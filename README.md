Apple's PLJ or Photo Library Journal (PLJ) binary Property List Journal (PLJ) format.
==================================================================

Apple Photos in Big Sur (and presumably earlier and later) uses two methods to store
archival data about the photos.

* a SQLITE database for interactive use in `photolibrary/database/Photos.sqlite`
* a set of property list journal (PLJ) files in `photolibrary/resources/journals/`

The sqlite database is _not backed up_ by Time Machine. The PLJ files are stored
by Time Machine. After a restore, these files can then rebuild the sqlite database.

Using `PLJ.py` to look at a file
--------------------------------

The `PLJ.py` script has a few routines to look at these files.

```
idempotent:apple-plj-format dgleich$ python3 PLJ.py ~/Pictures/Test-Library.photoslibrary/resources/journals/Asset-snapshot.plj
{'addedDate': datetime.datetime(2021, 11, 24, 19, 44, 56, 383155),
 'alternateImportImageDate': datetime.datetime(2013, 6, 8, 19, 50, 41),
 'avalanchePickType': 0,
 'cameraCaptureDevice': 0,
 'creatorBundleID': 'com.apple.Photos',
 'customRenderedValue': 0,
 'dateCreated': datetime.datetime(2013, 6, 8, 19, 50, 21),
 'deferredProcessingNeeded': 0,
 'depthStates': 0,
 'directory': '/Users/dgleich/Dropbox/Photos/Treetop',
 'duration': 17.633333333333333,
 'embeddedThumbnailHeight': 0,
 'embeddedThumbnailLength': 0,
 'embeddedThumbnailOffset': 0,
 'embeddedThumbnailWidth': 0,
 'exCameraMake': 'Apple',
 'exCameraModel': 'iPhone 4',
 'exCodec': 'avc1',
 'exDuration': 17.633333333333333,
 'exFps': 29.97167205810547,
 'exifTimestampString': '2013:06:08 15:50:21',
 'favorite': 0,
 'filename': 'IMG_2497.MOV',
 'groupingState': 0,
 'hasAdjustments': 0,
 'height': 720,
 'hidden': 0,
 'highFrameRateState': 0,
 'importedBy': 5,
 'importedByDisplayName': 'Photos',
 'inTrash': False,
 'kind': 1,
 'kindSubtype': 0,
[... and lots more ...]
```

The structure of a PLJ file.
----------------------------
The file is big long sequence of bytes that give a sequence of binary property list
data (bplist00 format). All encoding seems to be big endian.

```
File: [Record]*                # an array of records, 0 or more
Record: Header Payload?         # a header, followed by the payload (if needed)

# the header has a marker byte,
# followed by a CRC-16/ARC checksum of HeaderData, and
# the length of the remaining header data
Header: Byte==0x40 UInt16:HeaderChecksum UInt16:HeaderDataSize HeaderData

# the remaining header data has a marker byte (MAYBE I'm not sure what this byte is)
# followed by a RecordType byte (I've seen 0, 1 and 2 as values here)
# followed by two more fixed bytes (0x12 0x10) (MAYBE these might change, but I haven't seen that)
# followed by a 16-byte/128-bit value I believe is a UUID
# followed by optional header data if RecordType is 0 or 1
HeaderData: Byte==0x08 Byte:RecordType Byte==0x12 Byte==0x10 UInt128:RecordUUID HeaderDataOpt?

# RecordType seems to be 0x00, 0x01, or 0x02, where 0 is Create, 1 is Update, 2 might be delete
# if RecordType == 2, then there is no optional header data.
RecordType: 0x00:Create | 0x01:Update | 0x02:Delete??

# This optional Header data is only present if RecordType == 0x00 or 0x01
# It consists of two bytes I haven't understood, followed by 0x28,
# followed by a variable-size coded UInt that gives the Payload size (see below on UInt format)
# followed by another variable-size coded UInt that gives the PayloadCRC
HeaderDataOpt:  Byte:??? Byte:??? Byte==0x28 UIntVar:PayloadSize Byte==0x30 UIntVar:PayloadCRC

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

Current unknowns
----------------

There are a few mystery bytes above.
e.g. `Byte==0x40` a few of these may indicate other structures
that we haven't decoded yet.
