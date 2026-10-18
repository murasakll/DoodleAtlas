"""Audit block records separately from a library's chunk index and metadata."""
import struct

CHUNK_TAGS = set(range(43,66)) | {118,119}


def chunk_record(key):
    if len(key) not in (9,10,13,14):
        return None
    offset=8 if len(key) in (9,10) else 12
    tag=key[offset]
    if tag not in CHUNK_TAGS or (len(key)-offset == 2) != (tag==47):
        return None
    dimension=0 if offset==8 else struct.unpack_from('<i',key,8)[0]
    if dimension not in (0,1,2):
        return None
    cx,cz=struct.unpack_from('<ii',key)
    return dimension,cx,cz,tag


def audit_records(records,indexed):
    terrain={coord for coord,tags in records.items() if tags & {47,48}}
    markers={coord for coord,tags in records.items() if tags & {44,118}}
    metadata=set(records)-terrain-markers
    omitted=terrain-set(indexed)
    return {'block_record_chunks':len(terrain),'indexed_chunks':len(indexed),
            'omitted_block_record_chunks':len(omitted),
            'omitted_examples':[list(c) for c in sorted(omitted)[:30]],
            'metadata_only_chunks':len(metadata),
            'indexed_without_block_records':len(set(indexed)-terrain)}
