import datetime
import sys
from typing import Any, Dict, List, Union

AnyPacket = Dict[str, Any]

PaletteColor = int
HTMLColor = str
Color = Union[PaletteColor, HTMLColor]
Resources = str

_Number = Union[int, float]

NLUIntent = Dict[str, Any]

if sys.version_info < (3, 8):
    StatePacket = Dict[str, str]
    AnimationItem = Dict[str, Color]
    Animation = Dict[str, Any]
    InfoPacket = Dict[str, Any]
    EarsPacket = Dict[str, Any]
    ChoreographyURN = str
    CommandSequenceItem = Dict[str, Any]
    CommandPacket = Dict[str, Any]
    MessagePacket = Dict[str, Any]
    CancelPacket = Dict[str, str]
    WakeupPacket = Dict[str, str]
    SleepPacket = Dict[str, str]
    EventTypes = str
    ModePacket = Dict[str, Any]
    TestPacket = Dict[str, str]
    RfidWritePacket = Dict[str, Any]

    ResponseNFCOKPacketProto = Dict[str, str]
    ResponseNFCErrorPacketProto = Dict[str, str]
    ResponseNFCTimeoutPacketProto = Dict[str, str]

    ResponseOKPacketProto = Dict[str, str]
    ResponseErrorPacketProto = Dict[str, str]
    ResponseCanceledPacketProto = Dict[str, str]
    ResponseExpiredPacketProto = Dict[str, str]
    ResponseFailurePacketProto = Dict[str, str]
    ResponseGestaltPacketProto = Dict[str, Any]

    ResponseNFCOKPacket = Dict[str, str]
    ResponseNFCErrorPacket = Dict[str, str]
    ResponseNFCTimeoutPacket = Dict[str, str]

    ResponseOKPacket = Dict[str, str]
    ResponseErrorPacket = Dict[str, str]
    ResponseCanceledPacket = Dict[str, str]
    ResponseExpiredPacket = Dict[str, str]
    ResponseFailurePacket = Dict[str, str]
    ResponseGestaltPacket = Dict[str, Any]

    ServiceRequestPacket = Dict[str, str]

    ServicePacket = Dict[str, Any]

    ButtonEventType = str

    ASREventPacket = Dict[str, Any]
    ButtonEventPacket = Dict[str, Any]
    EarEventPacket = Dict[str, Any]
    EarsEventPacket = Dict[str, Any]
    RfidEventPacket = Dict[str, Any]

    ResponsePacketProto = Dict[str, Any]
    ResponsePacket = Dict[str, Any]
    EventPacket = Dict[str, Any]

    NabdPacket = Dict[str, Any]
else:
    from typing import Literal, TypedDict

    StateName = Literal[
        "asleep", "idle", "interactive", "playing", "recording"
    ]

    class StatePacket(TypedDict):
        type: Literal["state"]
        state: StateName

    class _InfoPacketBase(TypedDict):
        type: Literal["info"]
        info_id: str

    class AnimationItem(TypedDict, total=False):
        left: Color
        center: Color
        right: Color

    class Animation(TypedDict):
        tempo: _Number
        colors: List[AnimationItem]

    class InfoPacket(_InfoPacketBase, total=False):
        request_id: str
        animation: Animation

    class _EarsPacketBase(TypedDict):
        type: Literal["ears"]

    class EarsPacket(_EarsPacketBase, total=False):
        request_id: str
        left: int
        right: int
        event: bool

    ChoreographyURN = Union[Literal["urn:x-chor:streaming"], str]

    class CommandSequenceItem(TypedDict, total=False):
        audio: List[Resources]
        choreography: Union[Resources, ChoreographyURN]

    class _CommandPacketBase(TypedDict):
        type: Literal["command"]
        sequence: List[CommandSequenceItem]

    class CommandPacket(_CommandPacketBase, total=False):
        request_id: str
        expiration: datetime.datetime
        cancelable: bool

    class _MessagePacketBase(TypedDict):
        type: Literal["message"]
        body: List[CommandSequenceItem]

    class MessagePacket(_MessagePacketBase, total=False):
        request_id: str
        signature: CommandSequenceItem
        expiration: datetime.datetime
        cancelable: bool

    class CancelPacket(TypedDict):
        type: Literal["cancel"]
        request_id: str

    class _WakeupPacketBase(TypedDict):
        type: Literal["wakeup"]

    class WakeupPacket(_WakeupPacketBase, total=False):
        request_id: str

    class _SleepPacketBase(TypedDict):
        type: Literal["sleep"]

    class SleepPacket(_SleepPacketBase, total=False):
        request_id: str

    class _ModePacketBase(TypedDict):
        type: Literal["mode"]
        mode: Literal["idle", "interactive"]

    EventTypes = Union[Literal["asr", "button", "ears", "rfid/*"], str]

    class ModePacket(_ModePacketBase, total=False):
        events: List[EventTypes]
        request_id: str

    class _TestPacketBase(TypedDict):
        type: Literal["test"]
        test: str

    class TestPacket(_TestPacketBase, total=False):
        request_id: str

    class _RfidWritePacketBase(TypedDict):
        type: Literal["rfid_write"]
        uid: str
        picture: int
        app: int
        tech: str

    class RfidWritePacket(_RfidWritePacketBase, total=False):
        request_id: str
        timeout: _Number
        data: str

    class ResponseOKPacketProto(TypedDict):
        status: Literal["ok"]

    class _ResponseOKPacketBase(ResponseOKPacketProto):
        type: Literal["response"]

    class ResponseOKPacket(_ResponseOKPacketBase, total=False):
        request_id: str

    class ResponseCanceledPacketProto(TypedDict):
        status: Literal["canceled"]

    class _ResponseCanceledPacketBase(ResponseCanceledPacketProto):
        type: Literal["response"]

    class ResponseCanceledPacket(_ResponseCanceledPacketBase, total=False):
        request_id: str

    class ResponseExpiredPacketProto(TypedDict):
        status: Literal["expired"]

    class _ResponseExpiredPacketBase(ResponseExpiredPacketProto):
        type: Literal["response"]

    class ResponseExpiredPacket(_ResponseExpiredPacketBase, total=False):
        request_id: str

    ResponseErrorPacketProto = TypedDict(
        "ResponseErrorPacketProto",
        {"status": Literal["error"], "class": str, "message": str},
    )

    class _ResponseErrorPacketBase(ResponseErrorPacketProto):
        type: Literal["response"]

    class ResponseErrorPacket(_ResponseErrorPacketBase, total=False):
        request_id: str

    class ResponseFailurePacketProto(TypedDict):
        status: Literal["failure"]

    class _ResponseFailurePacketBase(ResponseFailurePacketProto):
        type: Literal["response"]

    class ResponseFailurePacket(_ResponseFailurePacketBase, total=False):
        request_id: str

    class ResponseNFCOKPacketProto(ResponseOKPacketProto, total=False):
        uid: str

    class _ResponseNFCOKPacketBase(ResponseNFCOKPacketProto):
        type: Literal["response"]

    class ResponseNFCOKPacket(_ResponseNFCOKPacketBase, total=False):
        request_id: str

    class ResponseNFCErrorPacketProto(ResponseErrorPacketProto, total=False):
        uid: str

    class _ResponseNFCErrorPacketBase(ResponseNFCErrorPacketProto):
        type: Literal["response"]

    class ResponseNFCErrorPacket(_ResponseNFCErrorPacketBase, total=False):
        request_id: str

    class ResponseNFCTimeoutPacketProto(TypedDict):
        status: Literal["timeout"]
        message: str

    class _ResponseNFCTimeoutPacketBase(ResponseNFCTimeoutPacketProto):
        type: Literal["response"]

    class ResponseNFCTimeoutPacket(_ResponseNFCTimeoutPacketBase, total=False):
        request_id: str

    class _ResponseGestaltPacketProtoBase(TypedDict):
        state: StateName
        connections: int
        hardware: str

    class ResponseGestaltPacketProto(
        _ResponseGestaltPacketProtoBase, total=False
    ):
        uptime: int

    class _ResponseGestaltPacketBase(ResponseGestaltPacketProto):
        type: Literal["response"]

    class ResponseGestaltPacket(_ResponseGestaltPacketBase, total=False):
        request_id: str

    class ServiceRequestPacket(TypedDict, total=False):
        request_id: str

    ServicePacket = Union[
        InfoPacket,
        EarsPacket,
        CommandPacket,
        MessagePacket,
        CancelPacket,
        WakeupPacket,
        SleepPacket,
        ModePacket,
        RfidWritePacket,
        TestPacket,
    ]

    class ASREventPacket(TypedDict):
        type: Literal["asr_event"]
        nlu: NLUIntent
        time: float

    ButtonEventType = Literal[
        "up",
        "down",
        "click",
        "hold",
        "click_and_hold",
        "double_click",
        "triple_click",
    ]

    class ButtonEventPacket(TypedDict):
        type: Literal["button_event"]
        event: ButtonEventType
        time: float

    class EarEventPacket(TypedDict):
        type: Literal["ear_event"]
        ear: Literal["left", "right"]
        time: float

    class EarsEventPacket(TypedDict):
        type: Literal["ears_event"]
        left: int
        right: int
        time: float

    class _RfidEventPacketBase(TypedDict):
        type: Literal["rfid_event"]
        tech: str
        uid: str
        event: Literal["removed", "detected"]
        support: Literal[
            "formatted", "foreign-data", "locked", "empty", "unknown"
        ]
        time: float

    class RfidEventPacket(_RfidEventPacketBase, total=False):
        locked: bool
        picture: str
        tag_info: dict
        app: str
        data: str

    _ResponseNFCPacketProto = Union[
        ResponseNFCOKPacketProto,
        ResponseNFCErrorPacketProto,
        ResponseNFCTimeoutPacketProto,
    ]

    ResponsePacketProto = Union[
        _ResponseNFCPacketProto,
        ResponseOKPacketProto,
        ResponseErrorPacketProto,
        ResponseCanceledPacketProto,
        ResponseExpiredPacketProto,
        ResponseFailurePacketProto,
        ResponseGestaltPacketProto,
    ]

    _ResponseNFCPacket = Union[
        ResponseNFCOKPacket, ResponseNFCErrorPacket, ResponseNFCTimeoutPacket
    ]

    ResponsePacket = Union[
        _ResponseNFCPacket,
        ResponseOKPacket,
        ResponseErrorPacket,
        ResponseCanceledPacket,
        ResponseExpiredPacket,
        ResponseFailurePacket,
        ResponseGestaltPacket,
    ]

    EventPacket = Union[
        ASREventPacket,
        ButtonEventPacket,
        EarEventPacket,
        EarsEventPacket,
        RfidEventPacket,
    ]

    NabdPacket = Union[ResponsePacket, StatePacket, EventPacket]
