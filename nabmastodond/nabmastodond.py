import sys
import asyncio
import re
from nabcommon import nabservice
from mastodon import Mastodon, StreamListener, MastodonError
from operator import attrgetter


class NabMastodond(nabservice.NabService, asyncio.Protocol, StreamListener):
    DAEMON_PIDFILE = "/run/nabmastodond.pid"

    RETRY_DELAY = 15 * 60  # Retry to reconnect every 15 minutes.
    NABPAIRING_MESSAGE_RE = (
        r"NabPairing (?P<cmd>Proposal|Acceptation|Rejection|Divorce|Ears "
        r'(?P<left>[0-9]+) (?P<right>[0-9]+)) - (?:<a href=")?'
        r"https://github.com/nabaztag2018/pynab"
    )
    PROTOCOL_MESSAGES = {
        "proposal": "Would you accept to be my spouse? "
        "(NabPairing Proposal - https://github.com/nabaztag2018/pynab)",
        "acceptation": "Oh yes, I do accept to be your spouse "
        "(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)",
        "rejection": "Sorry, I cannot be your spouse right now "
        "(NabPairing Rejection - https://github.com/nabaztag2018/pynab)",
        "divorce": "I think we should split. Can we skip the lawyers? "
        "(NabPairing Divorce - https://github.com/nabaztag2018/pynab)",
        "ears": "Let's dance (NabPairing Ears {left} {right} - "
        "https://github.com/nabaztag2018/pynab)",
    }

    def __init__(self):
        super().__init__()
        self.mastodon_client = None
        self.mastodon_stream_handle = None
        self.current_access_token = None
        self.listening_to_ears = False

    async def __config(self):
        from . import models

        return await models.Config.load_async()

    async def reload_config(self):
        await self.setup_streaming(True)
        await self.setup_initial_state()

    def close_streaming(self):
        if (
            self.mastodon_stream_handle
            and self.mastodon_stream_handle.connection
        ):
            self.mastodon_stream_handle.close()
        self.current_access_token = None
        self.mastodon_stream_handle = None
        self.mastodon_client = None

    def on_update(self, status):
        asyncio.run_coroutine_threadsafe(
            self.loop_update(self.mastodon_client, status), self.loop
        )

    def on_notification(self, notification):
        if (
            "type" in notification
            and notification["type"] == "mention"
            and "status" in notification
        ):
            asyncio.run_coroutine_threadsafe(
                self.loop_update(self.mastodon_client, notification["status"]),
                self.loop,
            )

    async def loop_update(self, mastodon_client, status):
        config = await self.__config()
        (status_id, status_date) = await self.process_status(
            config, mastodon_client, status
        )
        if status_id is not None and (
            config.last_processed_status_id is None
            or status_id > config.last_processed_status_id
        ):
            config.last_processed_status_id = status_id
        if (
            status_date is not None
            and status_date > config.last_processed_status_date
        ):
            config.last_processed_status_date = status_date
        await config.save_async()

    async def process_conversations(self, mastodon_client, conversations):
        config = await self.__config()
        max_date = config.last_processed_status_date
        max_id = config.last_processed_status_id
        conversations_last_statuses = map(
            attrgetter("last_status"), conversations
        )
        for status in sorted(
            conversations_last_statuses, key=attrgetter("id")
        ):
            (status_id, status_date) = await self.process_status(
                config, mastodon_client, status
            )
            if status_id is not None and (
                max_id is None or status_id > max_id
            ):
                max_id = status_id
            if status_date is not None and (
                status_date is None or status_date > max_date
            ):
                max_date = status_date
        config.last_processed_status_date = max_date
        config.last_processed_status_id = max_id
        await config.save_async()

    async def process_status(self, config, mastodon_client, status):
        try:
            status_id = status["id"]
            status_date = status["created_at"]
            skip = False
            if config.last_processed_status_id is not None:
                skip = status_id <= config.last_processed_status_id
            skip = skip or config.last_processed_status_date > status_date
            if not skip:
                await self.do_process_status(config, mastodon_client, status)
            return (status_id, status_date)
        except KeyError as e:
            print(
                f"Unexpected status from mastodon, missing slot {e}\n{status}"
            )
            return (None, None)

    async def do_process_status(self, config, mastodon_client, status):
        if status["visibility"] == "direct":
            sender_account = status["account"]
            sender_url = sender_account["url"]
            if (
                sender_url
                != "https://" + config.instance + "/@" + config.username
            ):
                sender = sender_account["acct"]
                if "@" not in sender:
                    sender = sender + "@" + config.instance
                if "display_name" in sender_account:
                    sender_name = sender_account["display_name"]
                else:
                    sender_name = sender_account["username"]
                type, params = self.decode_dm(status)
                if type is not None:
                    await self.transition_state(
                        config,
                        mastodon_client,
                        sender,
                        sender_name,
                        type,
                        params,
                        status["created_at"],
                    )

    async def transition_state(
        self,
        config,
        mastodon_client,
        sender,
        sender_name,
        type,
        params,
        message_date,
    ):
        current_state = config.spouse_pairing_state
        matching = (
            config.spouse_handle is not None and config.spouse_handle == sender
        )
        if current_state is None:
            if type == "proposal":
                config.spouse_handle = sender
                config.spouse_pairing_state = "waiting_approval"
                config.spouse_pairing_date = message_date
                await self.play_message("proposal_received", sender_name)
            elif type == "acceptation" or type == "ears":
                NabMastodond.send_dm(mastodon_client, sender, "divorce")
            # else ignore message
        elif current_state == "proposed":
            if matching and type == "rejection":
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
                await self.play_message("proposal_refused", sender_name)
            elif matching and type == "divorce":
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
                await self.play_message("proposal_refused", sender_name)
            elif matching and type == "acceptation":
                config.spouse_handle = sender
                config.spouse_pairing_state = "married"
                config.spouse_pairing_date = message_date
                await self.send_start_listening_to_ears()
                await self.play_message("proposal_accepted", sender_name)
            elif matching and type == "proposal":
                NabMastodond.send_dm(mastodon_client, sender, "acceptation")
                config.spouse_handle = sender
                config.spouse_pairing_state = "married"
                config.spouse_pairing_date = message_date
                await self.send_start_listening_to_ears()
                await self.play_message("proposal_accepted", sender_name)
            elif not matching and (type == "acceptation" or type == "ears"):
                NabMastodond.send_dm(mastodon_client, sender, "divorce")
            elif not matching and type == "proposal":
                NabMastodond.send_dm(mastodon_client, sender, "rejection")
            # else ignore
        elif current_state == "waiting_approval":
            if matching and type == "rejection":
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
            elif matching and type == "divorce":
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
                await self.play_message("pairing_cancelled", sender_name)
            elif matching and type == "acceptation":
                NabMastodond.send_dm(mastodon_client, sender, "divorce")
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
            elif type == "proposal":
                if not matching:
                    NabMastodond.send_dm(
                        mastodon_client, config.spouse_handle, "rejection"
                    )
                    config.spouse_handle = sender
                config.spouse_pairing_date = message_date
                await self.play_message("proposal_received", sender_name)
            elif matching and type == "acceptation":
                NabMastodond.send_dm(mastodon_client, sender, "divorce")
            elif not matching and (type == "acceptation" or type == "ears"):
                NabMastodond.send_dm(mastodon_client, sender, "divorce")
            # else ignore
        elif current_state == "married":
            if matching and type == "rejection":
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
                await self.send_stop_listening_to_ears()
                await self.play_message("pairing_cancelled", sender_name)
            elif matching and type == "divorce":
                config.spouse_handle = None
                config.spouse_pairing_state = None
                config.spouse_pairing_date = message_date
                await self.send_stop_listening_to_ears()
                await self.play_message("pairing_cancelled", sender_name)
            elif matching and type == "acceptation":
                config.spouse_pairing_date = message_date
            elif matching and type == "proposal":
                NabMastodond.send_dm(mastodon_client, sender, "acceptation")
                config.spouse_pairing_date = message_date
            elif not matching and (type == "acceptation" or type == "ears"):
                NabMastodond.send_dm(mastodon_client, sender, "divorce")
            elif not matching and type == "proposal":
                NabMastodond.send_dm(mastodon_client, sender, "rejection")
            elif matching and type == "ears":
                await self.play_message("ears", sender_name)
                config.spouse_left_ear_position = params["left"]
                config.spouse_right_ear_position = params["right"]
                config.spouse_pairing_date = message_date
                await self.send_ears(params["left"], params["right"])
            # else ignore

    async def play_message(self, message, sender_name):
        """
        Play pairing protocol message
        """
        if message == "ears":
            packet = (
                '{"type":"command",'
                '"sequence":[{"audio":["nabmastodond/communion.wav"]}]}\r\n'
            )
        elif message == "proposal_received":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmastodond/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmastodond/proposal_received.mp3"]}]}'
                "\r\n"
            )
        elif message == "proposal_refused":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmastodond/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmastodond/proposal_refused.mp3"]}]}'
                "\r\n"
            )
        elif message == "proposal_accepted":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmastodond/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmastodond/proposal_accepted.mp3"]}]}'
                "\r\n"
            )
        elif message == "pairing_cancelled":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmastodond/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmastodond/pairing_cancelled.mp3"]}]}'
                "\r\n"
            )
        elif message == "setup":
            packet = (
                '{"type":"message",'
                '"signature":{"audio":["nabmastodond/respirations/*.mp3"]},'
                '"body":[{"audio":["nabmastodond/setup.mp3"]}]}'
                "\r\n"
            )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    async def send_start_listening_to_ears(self):
        if self.listening_to_ears is False:
            packet = '{"type":"mode","mode":"idle","events":["ears"]}\r\n'
            self.writer.write(packet.encode("utf8"))
            await self.writer.drain()
            self.listening_to_ears = True

    async def send_stop_listening_to_ears(self):
        if self.listening_to_ears:
            packet = '{"type":"mode","mode":"idle","events":[]}\r\n'
            self.writer.write(packet.encode("utf8"))
            await self.writer.drain()
            self.listening_to_ears = False

    async def send_ears(self, left_ear, right_ear):
        packet = f'{{"type":"ears","left":{left_ear},"right":{right_ear}}}\r\n'
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    @staticmethod
    def send_dm(mastodon_client, target, message, params={}):
        """
        Send a DM following pairing protocol
        """
        message_str = NabMastodond.PROTOCOL_MESSAGES[message].format(**params)
        status = "@" + target + " " + message_str
        return mastodon_client.status_post(status, visibility="direct")

    def decode_dm(self, status):
        m = re.search(NabMastodond.NABPAIRING_MESSAGE_RE, status["content"])
        if m:
            if "Ears" in m.group("cmd"):
                return (
                    "ears",
                    {
                        "left": int(m.group("left")),
                        "right": int(m.group("right")),
                    },
                )
            return m.group("cmd").lower(), None
        return None, None

    async def setup_streaming(self, reloading=False):
        config = await self.__config()
        setup = (
            reloading
            and self.mastodon_client is None
            and config.spouse_handle is None
        )
        if config.access_token is None:
            self.close_streaming()
        else:
            if config.access_token != self.current_access_token:
                self.close_streaming()
            if self.mastodon_client is None:
                try:
                    self.mastodon_client = Mastodon(
                        client_id=config.client_id,
                        client_secret=config.client_secret,
                        access_token=config.access_token,
                        api_base_url="https://" + config.instance,
                    )
                    self.current_access_token = config.access_token
                    if setup:
                        await self.play_message("setup", config.spouse_handle)
                except MastodonUnauthorizedError:
                    self.current_access_token = None
                    config.access_token = None
                    await config.save_async()
                except MastodonError as e:
                    print(f"Unexpected mastodon error: {e}")
                    await asyncio.sleep(NabMastodond.RETRY_DELAY)
                    await self.setup_streaming()
            if (
                self.mastodon_client is not None
                and self.mastodon_stream_handle is None
            ):
                self.mastodon_stream_handle = self.mastodon_client.stream_user(
                    self, run_async=True, reconnect_async=True
                )
            if self.mastodon_client is not None:
                conversations = self.mastodon_client.conversations(
                    since_id=config.last_processed_status_id
                )
                await self.process_conversations(
                    self.mastodon_client, conversations
                )

    async def process_nabd_packet(self, packet):
        if packet["type"] == "ears_event":
            config = await self.__config()
            if config.spouse_pairing_state == "married":
                if self.mastodon_client:
                    await self.play_message("ears", config.spouse_handle)
                    config.spouse_left_ear_position = packet["left"]
                    config.spouse_right_ear_position = packet["right"]
                    await config.save_async()
                    NabMastodond.send_dm(
                        self.mastodon_client,
                        config.spouse_handle,
                        "ears",
                        {"left": packet["left"], "right": packet["right"]},
                    )

    async def setup_initial_state(self):
        config = await self.__config()
        if config.spouse_pairing_state == "married":
            await self.send_start_listening_to_ears()
            if config.spouse_left_ear_position is not None:
                await self.send_ears(
                    config.spouse_left_ear_position,
                    config.spouse_right_ear_position,
                )
        else:
            await self.send_stop_listening_to_ears()

    def run(self):
        super().connect()
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.setup_streaming())
        self.loop.run_until_complete(self.setup_initial_state())
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False  # signal to exit
            self.writer.close()
            self.close_streaming()
            tasks = asyncio.all_tasks(self.loop)
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                self.loop.run_until_complete(
                    t
                )  # give canceled tasks the last chance to run
            self.loop.close()


if __name__ == "__main__":
    NabMastodond.main(sys.argv[1:])
