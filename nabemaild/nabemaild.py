import logging
import sys
import smtplib
import ssl
from nabcommon.nabservice import NabService
from . import rfid_data


class NabEmaild(NabService):
    def __init__(self):
        super().__init__()
        self.__email = None

    async def reload_config(self):
        pass

    async def _send_email(self, email_add, subject):

        logging.info("sending an email to " + email_add)
        from . import models

        config = await models.Config.load_async()

        port = 465  # For SSL
        smtp_server = "smtp.gmail.com"
        sender_email = config.gmail_account
        password = config.gmail_passwd

        message = (
            "SUBJECT\n\n"
            "Bonjour, vous m'avez demandé de vous envoyer un email "
            "lorsque ce tag est vu.\n\n"
            "Voilà ! C'est fait.\n\n"
            "Votre Nabaztag\n\n"
            "Hello!\n\n"
            "You asked me a while ago to send you an email when I see this tag.\n\n"
            "Well, I've just seen it!\n\n"
            "Your Nabaztag"
        )

        message = message.replace("SUBJECT", subject)
        message = message.encode("utf-8")

        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(
                smtp_server, port, context=context
            ) as server:
                server.login(sender_email, password)
                server.sendmail(sender_email, email_add, message)
                return True
        except Exception as err:
            logging.error("_send_email" + str(err))
            return False

    async def process_nabd_packet(self, packet):
        if (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabemaild"
            and packet["event"] == "detected"
        ):

            (email, subject) = await rfid_data.read_data_ui(packet["uid"])
            await self._send_email(email, subject)


if __name__ == "__main__":
    NabEmaild.main(sys.argv[1:])
