import collections
import dataclasses
import gzip
import io
import struct
import typing

import numpy as np


__all__ = ["Encoder", "Decoder"]


class Encoder:
    def __init__(self):
        self._codecs = EncodeCodecs()
        self._seen_type_ids = set()
        self._buf_single = (
            bytearray()
        )  # scratch for assembling individual type descriptors, values
        self._buf_multi = bytearray()  # scratch for concatenating types, values

    def encode(self, val) -> bytes:
        self._buf_multi.clear()

        codec = self._codecs.find_codec(val)
        new_type_ids = self._codecs.wire_types.keys() - self._seen_type_ids
        for type_id in sorted(new_type_ids):
            self._buf_single.clear()
            go_int_codec.encode(self._buf_single, -type_id)
            go_wire_type_codec.encode(
                self._buf_single, self._codecs.wire_types[type_id]
            )
            self._copy_single()
            self._seen_type_ids.add(type_id)

        self._buf_single.clear()
        go_int_codec.encode(self._buf_single, self._codecs.type_ids[codec])
        if not isinstance(codec, GoStructCodec):
            self._buf_single.append(0)
        codec.encode(self._buf_single, val)
        self._copy_single()

        return bytes(self._buf_multi)

    def _copy_single(self):
        go_uint_codec.encode(self._buf_multi, len(self._buf_single))
        self._buf_multi.extend(self._buf_single)


@dataclasses.dataclass
class Stream:
    msg: io.BytesIO # Currently being parsed.
    rest: io.BytesIO

    def msg_done(self) -> bool:
        return self.msg.tell() >= len(self.msg.getvalue())

    def pop_msg(self):
        self.msg = self.rest
        msg_len = go_uint_codec.decode(None, self)
        assert msg_len > 0
        msg_bytes = self.rest.read(msg_len)
        assert len(msg_bytes) == msg_len
        self.msg = io.BytesIO(msg_bytes)
        # import sys; print(f"****** pop {msg_len} {self.msg.tell()} {len(self.msg.getvalue())}", file=sys.stderr)            
        # print([int(b) for b in self.msg.getvalue()[self.msg.tell():self.msg.tell()+100]], file=sys.stderr)

def new_stream(data: io.BytesIO) -> Stream:
    stream = Stream(None, data)
    stream.pop_msg()
    return stream


class Decoder:
    def __init__(self, known_types=tuple()):
        self._codecs = DecodeCodecs()
        for typ in known_types:
            self._codecs.register(typ)

    # TODO: Stream?
    def decode_one(self, data: io.BytesIO) -> typing.Any:
        "Decode one object. Returns None at EOF."

        stream = new_stream(data)
        type_id = self._decode_type_id(stream)
        codec = self._codecs.get_codec(type_id)
        if not isinstance(codec, GoStructCodec):
            assert stream.msg.read(1) == bytes([0])
        val = codec.decode(self, stream)
        # import sys; print(f"****** val decode_one {type_id} {val}", file=sys.stderr)            
        assert len(stream.msg.read()) == 0, "leftover data"
        return val

    def decode_all(self, data: bytes) -> typing.Tuple[typing.Any]:
        vals = []
        stream = io.BytesIO(data)
        while stream.tell() < len(stream.getvalue()):
            vals.append(self.decode_one(stream))
        return tuple(vals)

    def skip_one(self, data: io.BytesIO):
        unused_stream = new_stream(data)
        return

    def _decode_type_id(self, stream: Stream) -> int:
        while True:
            if stream.msg_done():
                stream.pop_msg()

            type_id = go_int_codec.decode(None, stream)
            if type_id >= 0:
                # import sys; print(f"****** val {type_id}", file=sys.stderr)            
                return type_id
            # import sys; print(f"****** type start {type_id}", file=sys.stderr)            
            # if type_id in (-37, -71):
            #     print([int(b) for b in stream.msg.getvalue()[stream.msg.tell():stream.msg.tell()+1000]], file=sys.stderr)
            wire_type = go_wire_type_codec.decode(None, stream)
            self._codecs.add_codec(-type_id, wire_type)
            # import sys; print(f"****** type add {type_id} -> {wire_type}", file=sys.stderr)            
            # import sys; print(f"next: {[int(b) for b in stream.msg.getvalue()[stream.msg.tell():stream.msg.tell()+10]]}", file=sys.stderr)


class GoCodec:
    # TODO: Use io.BytesIO?
    def encode(self, buf: bytearray, val: typing.Any):
        """
        Appends gob-encoded val onto buf.
        """
        raise NotImplementedError()

    def decode(self, decoder: Decoder) -> typing.Any:
        raise NotImplementedError()


@dataclasses.dataclass
class GoInterfaceValue:
    concrete_type: str
    concrete_val: typing.Any


@dataclasses.dataclass
class GoCustomValue:
    raw: bytes


@dataclasses.dataclass(frozen=True)
class GoInterfaceCodec(GoCodec):
    # TODO: encode.

    def decode(self, decoder: Decoder, stream: Stream) -> str:
        concrete_type = go_string_codec.decode(None, stream)
        if concrete_type == "":
            return GoInterfaceValue("", None)
        # import sys; print(f"****** iface {concrete_type} ...", file=sys.stderr)            
        type_id = decoder._decode_type_id(stream)
        # msg_len = go_uint_codec.decode(None, stream)
        # msg_bytes = stream.msg.read(msg_len)
        # assert len(msg_bytes) == msg_len
        sub_stream = new_stream(stream.msg)
        # import sys; print(f"****** iface sub {len(sub_stream.msg.getvalue())}", file=sys.stderr)            
        # import sys; print(f"****** iface {concrete_type} {type_id} {unused_msg_len}", file=sys.stderr)            
        # print([int(b) for b in stream.msg.getvalue()[stream.msg.tell():stream.msg.tell()+unused_msg_len]], file=sys.stderr)
        codec = decoder._codecs.get_codec(type_id)
        if not isinstance(codec, GoStructCodec):
            assert sub_stream.msg.read(1) == bytes([0])
        val = GoInterfaceValue(concrete_type, codec.decode(decoder, sub_stream))
        leftover = sub_stream.msg.read()
        assert len(leftover) == 0, f"leftover data ({len(leftover)}) {[int(b) for b in leftover[:100]]}"
        # import sys; print(f"****** val iface decode {type_id} {val}", file=sys.stderr)            
        return val


@dataclasses.dataclass(frozen=True)
class GoUintCodec(GoCodec):
    def encode(self, buf: bytearray, n: int):
        if n < 0:
            raise ValueError(n)
        if n <= 0x7F:
            buf.append(n)
            return
        nbytes = (n.bit_length() + 7) // 8
        buf.append(256 - nbytes)
        buf.extend(struct.pack(">Q", n)[-nbytes:])

    def decode(self, unused_decoder: Decoder, stream: Stream) -> int:
        n = int(stream.msg.read(1)[0])
        if n <= 0x7F:
            return n
        nbytes = 256 - n
        buf = bytearray(struct.calcsize(">Q"))
        buf[-nbytes:] = stream.msg.read(nbytes)
        (n,) = struct.unpack(">Q", buf)
        return n


@dataclasses.dataclass(frozen=True)
class GoIntCodec(GoCodec):
    def encode(self, buf: bytearray, n: int):
        go_uint_codec.encode(buf, n << 1 if n >= 0 else (~n << 1) | 1)

    def decode(self, decoder: Decoder, stream: Stream) -> int:
        n = go_uint_codec.decode(None, stream)
        return ~(n >> 1) if (n & 1) else (n >> 1)


@dataclasses.dataclass(frozen=True)
class GoBoolCodec(GoCodec):
    def encode(self, buf: bytearray, b: bool):
        go_uint_codec.encode(buf, 1 if b else 0)

    def decode(self, unused_decoder: Decoder, stream: Stream) -> bool:
        return {0: False, 1: True}[go_uint_codec.decode(None, stream)]


@dataclasses.dataclass(frozen=True)
class GoFloatCodec(GoCodec):
    def encode(self, buf: bytearray, f: float):
        (byte_reversed,) = struct.unpack(">Q", struct.pack("<d", f))
        go_uint_codec.encode(buf, byte_reversed)

    def decode(self, unused_decoder: Decoder, stream: Stream) -> float:
        byte_reversed = go_uint_codec.decode(None, stream)
        return struct.unpack("<d", struct.pack(">Q", byte_reversed))[0]


@dataclasses.dataclass(frozen=True)
class GoBytesCodec(GoCodec):
    def encode(self, buf: bytearray, b):
        go_uint_codec.encode(buf, len(b))
        buf.extend(b)

    def decode(self, unused_decoder: Decoder, stream: Stream) -> bytes:
        n = go_uint_codec.decode(None, stream)
        val = stream.msg.read(n)
        assert len(val) == n
        return val


@dataclasses.dataclass(frozen=True)
class GoStringCodec(GoCodec):
    def encode(self, buf: bytearray, s):
        go_bytes_codec.encode(buf, s.encode("utf-8"))

    def decode(self, unused_decoder: Decoder, stream: Stream) -> str:
        return go_bytes_codec.decode(None, stream).decode("utf-8")


@dataclasses.dataclass(frozen=True)
class GoSliceCodec(GoCodec):
    elem: GoCodec

    def encode(self, buf: bytearray, s: collections.abc.Sequence):
        go_uint_codec.encode(buf, len(s))
        for elem in s:
            self.elem.encode(buf, elem)

    def decode(self, decoder: Decoder, stream: Stream) -> list:
        n = go_uint_codec.decode(None, stream)
        return [self.elem.decode(decoder, stream) for _ in range(n)]


@dataclasses.dataclass(frozen=True)
class GoArrayCodec(GoCodec):
    elem: GoCodec
    len: int

    # encode not supported; see TODO below.

    def decode(self, decoder: Decoder, stream: Stream) -> list:
        n = go_uint_codec.decode(decoder, stream)
        assert n <= self.len, f"array len {self.len} got {n} elements"
        return [self.elem.decode(decoder, stream) for _ in range(n)] + ([None] * (self.len - n))


@dataclasses.dataclass(frozen=True)
class GoMapCodec(GoCodec):
    key: GoCodec
    elem: GoCodec

    def encode(self, buf: bytearray, m: collections.abc.Mapping):
        go_uint_codec.encode(buf, len(m))
        for k, v in m.items():
            self.key.encode(buf, k)
            self.elem.encode(buf, v)

    def decode(self, decoder: Decoder, stream: Stream) -> dict:
        d = {}
        for _ in range(go_uint_codec.decode(None, stream)):
            k, v = self.key.decode(decoder, stream), self.elem.decode(decoder, stream)
            d[k] = v
        return d


@dataclasses.dataclass(frozen=True)
class GoStructCodec(GoCodec):
    DataClass: type
    fields: typing.Tuple[GoCodec]

    def encode(self, buf: bytearray, d):
        delta = 0
        for codec, field in zip(self.fields, dataclasses.fields(d)):
            delta += 1
            elem = getattr(d, field.name)
            if elem is not None:
                go_uint_codec.encode(buf, delta)
                codec.encode(buf, elem)
                delta = 0
        go_uint_codec.encode(buf, 0)

    def decode(self, decoder: Decoder, stream: Stream):  # -> self.DataClass
        fields = dataclasses.fields(self.DataClass)
        vals = {}
        idx = -1
        while True:
            delta = go_uint_codec.decode(None, stream)
            if delta == 0:
                break
            idx += delta
            # if idx >= len(self.fields):
            #     print(f"error! struct: {self.DataClass}, {fields}, {idx}, {vals}")
            # import sys; print(f"struct field: {self.DataClass.__name__}.{fields[idx].name}", file=sys.stderr)
            vals[fields[idx].name] = self.fields[idx].decode(decoder, stream)
        # import sys; print(f"done struct: {self.DataClass}. vals: {vals}", file=sys.stderr)
        return self.DataClass(**vals)


_numpy_custom_prefix = b"pygo.numpy:"


@dataclasses.dataclass(frozen=True)
class GoCustomDecoder(GoCodec):
    def encode(self, buf: bytearray, d):
        raise NotImplementedError("GoCustomDecoder is decode-only; use a specific custom type encoder")

    def decode(self, decoder: Decoder, stream: Stream):
        val = go_bytes_codec.decode(None, stream)
        if val.startswith(_numpy_custom_prefix):
            val = val[len(_numpy_custom_prefix) :]
            with gzip.GzipFile(fileobj=io.BytesIO(val), mode="rb") as f:
                return np.load(f)
        else:
            return GoCustomValue(val)


@dataclasses.dataclass(frozen=True)
class GoCustomEncoderNumpy(GoCodec):
    def encode(self, buf: bytearray, d):
        file = io.BytesIO()
        with gzip.GzipFile(fileobj=file, mode="wb") as f:
            np.save(f, d)
        buf.extend(_numpy_custom_prefix)
        buf.extend(file.getvalue())

    def decode(self, decoder: Decoder, stream: Stream):
        raise NotImplementedError("use combined GoCustomDecoder for decode")


@dataclasses.dataclass(frozen=True)
class GoCommonType:
    name: str = ""
    id: int = 0


@dataclasses.dataclass(frozen=True)
class GoArrayType:
    common: GoCommonType
    elem: int
    len: int


@dataclasses.dataclass(frozen=True)
class GoSliceType:
    common: GoCommonType
    elem: int


@dataclasses.dataclass(frozen=True)
class GoMapType:
    common: GoCommonType
    key: int
    elem: int


@dataclasses.dataclass(frozen=True)
class GoFieldType:
    name: str
    id: int


@dataclasses.dataclass(frozen=True)
class GoStructType:
    common: GoCommonType
    fields: typing.Tuple[GoFieldType] = tuple()


@dataclasses.dataclass(frozen=True)
class GoCustomType:
    common: GoCommonType


@dataclasses.dataclass(frozen=True)
class GoWireType:
    array_type: GoArrayType = None
    slice_type: GoSliceType = None
    struct_type: GoStructType = None
    map_type: GoMapType = None
    gob_encoder_type: GoCustomType = None
    binary_marshaler_type: GoCustomType = None
    text_marshaler_type: GoCustomType = None


go_uint_codec = GoUintCodec()
go_int_codec = GoIntCodec()
go_bool_codec = GoBoolCodec()
go_float_codec = GoFloatCodec()
go_bytes_codec = GoBytesCodec()
go_string_codec = GoStringCodec()
go_interface_codec = GoInterfaceCodec()

go_custom_decoder = GoCustomDecoder()
go_custom_encoder_numpy = GoCustomEncoderNumpy()

go_common_type_codec = GoStructCodec(GoCommonType, (go_string_codec, go_int_codec))
go_array_type_codec = GoStructCodec(
    GoArrayType, (go_common_type_codec, go_int_codec, go_int_codec)
)
go_slice_type_codec = GoStructCodec(GoSliceType, (go_common_type_codec, go_int_codec))
go_map_type_codec = GoStructCodec(
    GoMapType, (go_common_type_codec, go_int_codec, go_int_codec)
)
go_field_type_codec = GoStructCodec(GoFieldType, (go_string_codec, go_int_codec))
go_struct_type_codec = GoStructCodec(
    GoStructType, (go_common_type_codec, GoSliceCodec(go_field_type_codec))
)
go_custom_type_codec = GoStructCodec(GoCustomType, (go_common_type_codec,))
go_wire_type_codec = GoStructCodec(
    GoWireType,
    (
        go_array_type_codec,
        go_slice_type_codec,
        go_struct_type_codec,
        go_map_type_codec,
        go_custom_type_codec,
        go_custom_type_codec,
        go_custom_type_codec,
    ),
)


_DEFAULT_TYPE_IDS = {
    go_bool_codec: 1,
    go_int_codec: 2,
    go_uint_codec: 3,
    go_float_codec: 4,
    go_bytes_codec: 5,
    go_string_codec: 6,
    # TODO: complex
    go_interface_codec: 8,
    go_wire_type_codec: 16,
    go_array_type_codec: 17,
    go_common_type_codec: 18,
    go_slice_type_codec: 19,
    go_map_type_codec: 23,
}


class EncodeCodecs:
    type_ids: typing.Dict[GoCodec, int]
    next_type_id: int
    wire_types: typing.Dict[int, GoWireType]

    def __init__(self):
        self.type_ids = {**_DEFAULT_TYPE_IDS}
        self.next_type_id = 65  # It seems like encoding/gob uses this.
        self.wire_types = {}

    def find_codec(self, val):
        by_type = _codec_for_type(type(val))
        if by_type:
            return by_type

        if isinstance(val, collections.abc.Sequence):
            if len(val) == 0:
                raise NotImplementedError("empty sequence")
            elem_codec = self.find_codec(val[0])
            codec = GoSliceCodec(elem_codec)
            type_id = self._get_or_create_type_id(codec)
            if not type_id in self.wire_types:
                self.wire_types[type_id] = GoWireType(
                    slice_type=GoSliceType(
                        GoCommonType(None, type_id), self.type_ids[elem_codec]
                    )
                )
            return codec
            # TODO: Allow encoding arrays, perhaps using a Python wrapper to mark them.

        if isinstance(val, collections.abc.Mapping):
            if len(val) == 0:
                raise NotImplementedError("empty mapping")
            key_codec, elem_codec = map(self.find_codec, next(iter(val.items())))
            codec = GoMapCodec(key_codec, elem_codec)
            type_id = self._get_or_create_type_id(codec)
            if not type_id in self.wire_types:
                self.wire_types[type_id] = GoWireType(
                    map_type=GoMapType(
                        GoCommonType(None, type_id),
                        self.type_ids[key_codec],
                        self.type_ids[elem_codec],
                    )
                )
            return codec

        if dataclasses.is_dataclass(val):
            fields = dataclasses.fields(val)
            codec = GoStructCodec(
                type(val),
                tuple(
                    # Try type-based lookup (works even if field is unset). Fall
                    # back to value-based when necessary.
                    _codec_for_type(field.type)
                    or self.find_codec(getattr(val, field.name))
                    for field in fields
                ),
            )
            type_id = self._get_or_create_type_id(codec)
            if not type_id in self.wire_types:
                self.wire_types[type_id] = GoWireType(
                    struct_type=GoStructType(
                        GoCommonType(type(val).__name__, type_id),
                        tuple(
                            GoFieldType(field.name, self.type_ids[field_codec])
                            for field, field_codec in zip(fields, codec.fields)
                        ),
                    )
                )
            return codec

        if isinstance(val, np.ndarray):
            type_id = self._get_or_create_type_id(go_custom_encoder_numpy)
            self.wire_types[type_id] = GoWireType(
                binary_marshaler_type=GoCustomType(GoCommonType(id=type_id))
            )
            return go_custom_encoder_numpy

        raise NotImplementedError(val)

    def _get_or_create_type_id(self, codec: GoCodec) -> int:
        if codec not in self.type_ids:
            self.type_ids[codec] = self.next_type_id
            self.next_type_id += 1
        return self.type_ids[codec]


def _codec_for_type(typ: type):
    "Return codec for typ, else None (if codec is value-dependent)."
    if type(typ) is not type:
        return None
    if issubclass(typ, bool):
        return go_bool_codec
    # TODO: Support uint. Maybe with a wrapper on the Python side?
    if issubclass(typ, int):
        return go_int_codec
    if issubclass(typ, float):
        return go_float_codec
    if issubclass(typ, (bytes, bytearray)):
        return go_bytes_codec
    if issubclass(typ, str):
        return go_string_codec
    return None


class DecodeCodecs:
    _codecs: typing.Dict[int, typing.Union[GoCodec, typing.Callable[[], GoCodec]]]
    """
    _codecs is a sometimes-lazy mapping of type id -> codec.
    
    Lazy is required when an outer type (that refers to some nested type) is sent before the
    nested one. (Note: "encoding/gob" only requires the nested type is sent before the first value.)
    Lazy entries are replaced with their `GoCodec` result after first evaluation.
    """

    _registered: typing.Dict[str, type]
    "_registered contains dataclass types that will be used if they match a wire type (by name)."

    def __init__(self):
        self._codecs = {type_id: codec for codec, type_id in _DEFAULT_TYPE_IDS.items()}
        self._registered = {}

    def add_codec(self, type_id: int, wire_type: GoWireType):
        # We use type_id even if t.common.id is different. This happened with a GobEncoder object;
        # not sure if there are other circumstances where it can happen, too.

        if wire_type.array_type:
            t = wire_type.array_type
            self._codecs[type_id] = lambda: GoArrayCodec(self.get_codec(t.elem), t.len)
        if wire_type.slice_type:
            t = wire_type.slice_type
            self._codecs[type_id] = lambda: GoSliceCodec(self.get_codec(t.elem))
        if wire_type.struct_type:
            t = wire_type.struct_type
            # TODO: Field types?
            if t.common.name in self._registered:
                datacls = self._registered[t.common.name]
                # TODO: Check compatibility with wire type.
                # TODO: Mark as "used"?
            else:
                datacls = dataclasses.make_dataclass(
                    t.common.name, [(f.name, typing.Any, None) for f in t.fields]
                )
            self._codecs[type_id] = lambda: GoStructCodec(
                datacls, tuple(self.get_codec(f.id) for f in t.fields),
            )
        if wire_type.map_type:
            t = wire_type.map_type
            self._codecs[type_id] = lambda: GoMapCodec(
                self.get_codec(t.key), self.get_codec(t.elem),
            )
        custom_type = (
            wire_type.gob_encoder_type
            or wire_type.binary_marshaler_type
            or wire_type.text_marshaler_type
        )
        if custom_type:
            self._codecs[type_id] = go_custom_decoder

    def get_codec(self, type_id: int) -> GoCodec:
        codec = self._codecs[type_id]
        if callable(codec):
            codec = codec()
            self._codecs[type_id] = codec
        return codec

    def register(self, typ: type):
        assert dataclasses.is_dataclass(typ), f"expected dataclass: {typ}"
        if typ in self._registered:
            return
        self._registered[typ.__name__] = typ
        for field in dataclasses.fields(typ):
            if dataclasses.is_dataclass(field.type):
                self.register(field.type)
