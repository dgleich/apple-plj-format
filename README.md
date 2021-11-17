Apple's BPJ or Binary Property list Journal format.
==================================================

Apple Photos in Big Sur (and presumably earlier and later) uses two methods to store 
archival data about the photos. 

* a SQLITE database for interactive use in `photolibrary/database/Photos.sqlite`
* a set of BPJ files in `photolibrary/resources/journals/`

The sqlite database is _not backed up_ by Time Machine. The BPJ files are stored
by Time Machine. After a restore, these files can then rebuild the sqlite database.

The structure of a BPJ file.
----------------------------
The file is big long sequence of bytes. All encoding seems to be big endian. 

```

File: [Record]*                # an array of records
Record: Header Payload         # a header, followed by the payload 

# the header has a marker byte, 
# followed by a CRC-16/ARC checksum of HeaderData, and
# the length of the remaining header data
Header: Byte==0x40 UInt16:HeaderChecksum UInt16:HeaderDataSize HeaderData 

# the remaining header data has a marker byte ?? maybe, I'm not sure what this byte is
# followed by a RecordType byte (I've seen 0, 1 and 2 as values here)
# followed by two more fixed bytes (0x12 0x10) ?? these might change, but I haven't seen that 
# followed by a 16-byte/ 128-bit UUID
# followed by optional header data if RecordType is 0 or 1
HeaderData: Byte==0x08 Byte:RecordType Byte==0x12 Byte==0x10 UInt128:RecordUUID HeaderDataOpt?

# RecordType seems to be 0, 1, or 2, where 0x00 is Create, 0x01 is Update, 0x02 might be delete?
# if RecordType == 0x02, then there is no optional header data. 
RecordType: 0x00:Create | 0x01:Update | 0x02:Delete??

# This optional Header data is only present if RecoreType == 0x00 or 0x01 
# It consists of two bytes I haven't understood, followed by 0x28,
# followed by a variable-size coded UInt that gives the Payload size (see below on UInt format)
# followed by another variable-size coded UInt that gives the PayloadCRC 
HeaderDataOpt:  Byte:??? Byte:??? Byte==0x28 UIntVar:PayloadSize UIntVar:PayloadCRC

UIntVar is a variable length unsigned int-encoding. The high-bit (0x80) is used as the
   continuation character. See below for a program to decode in Python. Here are two
   examples. 
   
   511 = 0b11111111 0b00000011 = 1*(127)+ 128*(3) # the () values are from the bits in each byte
   20085 = 0b11110101 0b10011100 0b00000001 = 1*(117) + 128*(28) + 128*128*(1)
   
   
Payload: Byte*PayloadSize 

# Payload has always been a binary property list. 
# Internal references may use the RecordUUID to make links.

```

Variable-Length Integer encoding
--------------------------------
I'm fairly sure this is some standard, but since I don't know which one off
the top of my head, here is Python code to encode and decode these variable
length integers.

```
def _encode_uint(val):
  # allocate a 9 byte buffer to start
  bytevals = bytearray()
  while val > 127:
    bytevals.append((val & 127) | 128) # push the 7-low order bits and set high-bit
    val = val >> 7 # truncate the 7-low order bits
  bytevals.append(val & 127) # but don't set high-order bit
  val -= bytevals[-1]
  assert(val == 0)
  return bytes(bytevals)

def _decode_uint(bytes, start_offset):
  curbyte = start_offset
  val = 0
  offset = 1
  while bytes[curbyte] & 0b10000000 > 0: # test for high bit
    val += offset*(bytes[curbyte] & 0b01111111)   # mask out other bits
    offset *= 128 # scoot up by 7 bytes
    curbyte += 1
  val += bytes[curbyte]*offset
  return val, curbyte - start_offset + 1

# And a usage example testing all values up to 100000
for i in range(100000):
  assert(_decode_uint(_encode_uint(i), 0)[0] == i)
```

