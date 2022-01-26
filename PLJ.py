#!/usr/bin/env

# needed for CRC calculation.
import zlib
# needed for HeaderData type
from typing import NamedTuple

class PLJHeaderData(NamedTuple):
    """a docstring"""
    record_type: int
    payload_size: int
    payload_crc: int
    unk_byte1: int
    unk_byte2: int
    uuid: bytes
    rawdata: bytes

# from https://stackoverflow.com/questions/35205702/calculating-crc16-in-python
# and from
# https://github.com/tpircher/pycrc/blob/master/pycrc/algorithms.py
#  pycrc -- parameterisable CRC calculation utility and C source code generator
#
#  Copyright (c) 2006-2017  Thomas Pircher  <tehpeh-web@tty1.net>
def _reflect(data, width):
  res = data & 0x01
  for dummy_i in range(width - 1):
    data >>= 1
    res = (res << 1) | (data & 0x01)
  return res

def crc16(data:bytes):
  xor_in = 0x0000  # initial value
  xor_out = 0x0000  # final XOR value
  poly = 0x8005  # generator polinom (normal form)

  reg = xor_in
  for octet in data:
    octet = _reflect(octet, 8)
    for i in range(8):
      topbit = reg & 0x8000
      if octet & (0x80 >> i):
        topbit ^= 0x8000
      reg <<= 1
      if topbit:
        reg ^= poly
    reg &= 0xFFFF
  # reflect out
  reg = _reflect(reg, 16)
  return reg ^ xor_out

class TestClass:
  @classmethod
  def myfun(cls, data):
    print("myfun: ", data)

  def __init__(self, mydata):
    self.data = mydata

  def display(self):
    self.myfun(self.data)

def encode_varlen_uint(val):
  # allocate a 9 byte buffer to start
  bytevals = bytearray()
  while val > 127:
    bytevals.append((val & 127) | 128) # push the 7-low order bits and set high-bit
    val = val >> 7 # truncate the 7-low order bits
  bytevals.append(val & 127) # but don't set high-order bit
  val -= bytevals[-1]
  assert(val == 0)
  return bytes(bytevals)

def decode_varlen_uint(bytes, start_offset):
  curbyte = start_offset
  val = 0
  offset = 1
  while bytes[curbyte] & 0b10000000 > 0: # test for high bit
    val += offset*(bytes[curbyte] & 0b01111111)   # mask out other bits
    offset *= 128 # scoot up by 7 bytes
    curbyte += 1
  val += bytes[curbyte]*offset
  return val, curbyte - start_offset + 1



"""This class just gives an iterator over the simple PLJ data. It also
gives tools for decoding the bytes that are returned."""
class RawPLJReader:
  def __init__(self, fp):
    self.fp = fp

  @classmethod
  def decode_header(cls, header):
    assert(header[0] == 0x40)
    crc = int.from_bytes(header[1:3], "big")
    datalen = int.from_bytes(header[3:5], "big")
    return datalen, crc

  @classmethod
  def _decode_payload_info(cls, payload_info):
    byte1 = payload_info[0]
    byte2 = payload_info[1]
    assert(payload_info[2] == 0x28)
    payload_size, datalen = decode_varlen_uint(payload_info, 3)
    assert(payload_info[3+datalen] == 0x30)
    payload_crc, datalen = decode_varlen_uint(payload_info, 3+datalen+1)

    return byte1, byte2, payload_size, payload_crc

  """
  This
  """
  @classmethod
  def decode_headerdata(cls, header_data):
    assert(header_data[0] == 0x08)
    recordtype = header_data[1]
    assert(header_data[2] == 0x12)
    assert(header_data[3] == 0x10)

    uuid = header_data[4:20]

    if recordtype != 2:
      byte1, byte2, payload_size, payload_crc = cls._decode_payload_info(
        header_data[20:])
    else:
      byte1 = 0
      byte2 = 0
      payload_size = 0
      payload_crc = 0

    #Byte==0x08 Byte:RecordType Byte==0x12 Byte==0x10 UInt128:RecordUUID
    return PLJHeaderData(uuid=uuid, record_type = recordtype,
        rawdata = header_data,
        payload_size=payload_size, payload_crc=payload_crc,
        unk_byte1 = byte1, unk_byte2 = byte2
        )

  @classmethod
  def validate_header(cls, header, header_data):
    header_data_length, header_data_crc = cls.decode_header(header)
    assert(crc16(header_data) == header_data_crc)

  @classmethod
  def validate_payload(cls, header_data, payload):
    #_print_bytes(header_data.rawdata)
    #_print_bytes(header_data.payload_crc.to_bytes(4, byteorder="big"))
    #_print_bytes(zlib.crc32(payload).to_bytes(4, byteorder="big"))
    assert(header_data.payload_crc == zlib.crc32(payload))

  """This is not a thread-safe iterator."""
  def __iter__(self, *, validate=True):
    self.fp.seek(0)
    recordnum = 0
    while True:
      recordnum += 1
      header = self.fp.read(5)
      if len(header) == 0:
        break # break out of the loop
      elif len(header) < 5:
        bytenum = self.fp.tell() - len(header)
        raise(IOError("insufficient header bytes at record number %i at byte %i"%(
                        recordnum, bytenum)))

      # otherwise, we are okay to decode
      header_data_length, header_data_crc = self.decode_header(header)

      header_data = self.fp.read(header_data_length)
      if len(header_data) < header_data_length:
        bytenum = self.fp.tell() - len(header_data)
        raise(IOError("insufficient header data at record number %i at byte %i"%(
                        recordnum, bytenum)))

      if validate:
        self.validate_header(header, header_data)

      data = self.decode_headerdata(header_data)

      payload = self.fp.read(data.payload_size)
      if len(payload) < data.payload_size:
        bytenum = self.fp.tell() - len(payload)
        raise(IOError("insufficient payload data at record number %i at byte %i"%(
                        recordnum, bytenum)))

      if validate:
        self.validate_payload(data, payload)

      yield (header, data, payload)


def _print_bytes(bytes, maxlen=40):
  for startbyte in range(0, len(bytes), maxlen):
    for bytenum in range(startbyte, min(len(bytes), startbyte+maxlen)):
      b = bytes[bytenum]
      hval = hex(b)[2:]
      if len(hval) == 1:
        hval = '0'+hval
      print(hval  , "", end="")
      print(end="")
    print() # newline

class PLJWriter:
  """ This is still very specific... and needs more testing! """
  def __init__(self, fp):
    self.fp = fp

  def write_payload(self, headerdata, payload):
    payload_header = bytearray()
    payload_header.append(0x08)
    payload_header.append(headerdata.record_type)
    payload_header.append(0x12)
    payload_header.append(0x10)
    payload_header.extend(headerdata.uuid)

    if headerdata.record_type != 2:
      payload_header.append(headerdata.unk_byte1)
      payload_header.append(headerdata.unk_byte2)
      payload_header.append(0x28)
      payload_header.extend(encode_varlen_uint(len(payload)))
      payload_header.append(0x30)
      payload_header.extend(encode_varlen_uint(zlib.crc32(payload)))

    payload_header_bytes = bytes(payload_header)

    record_header = bytearray()
    record_header.append(0x40)
    payload_header_crc = crc16(payload_header_bytes)
    record_header.extend(payload_header_crc.to_bytes(2, "big"))
    record_header.extend(len(payload_header).to_bytes(2, "big"))

    self.fp.write(record_header)
    self.fp.write(payload_header_bytes)
    self.fp.write(payload)


if __name__ == '__main__':
  import sys, plistlib, pprint
  fn = sys.argv[1]
  with open(fn, "rb") as f:
    records = RawPLJReader(f)
    for (header, headerdata, payload) in records:
      #print("Header = ")
      #_print_bytes(header)
      #print("Record = ")
      if len(payload) > 0:
        out = plistlib.loads(payload)
        pprint.pprint(out)
      else:
        pprint.pprint({})
