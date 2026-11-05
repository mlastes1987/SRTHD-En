"""Small Thumb-2 patch helpers for the fixed-address Vita executable."""
import re
import struct
import capstone


def branch(site,target,link=False):
    delta=target-site-4
    if delta&1 or not -(1<<24)<=delta<(1<<24):raise ValueError('Thumb branch range')
    s=(delta>>24)&1;i1=(delta>>23)&1;i2=(delta>>22)&1
    j1=1^(i1^s);j2=1^(i2^s)
    return struct.pack('<HH',0xf000|s<<10|(delta>>12)&1023,
                       (0xd000 if link else 0x9000)|j1<<13|j2<<11|(delta>>1)&2047)


def immediate(original,value):
    """Rewrite a Thumb MOVW/MOVT immediate, retaining opcode and destination."""
    a,b=struct.unpack('<HH',original)
    a=(a&~0x040f)|((value>>12)&15)|((value>>11)&1)<<10
    b=(b&~0x70ff)|((value>>8)&7)<<12|(value&255)
    return struct.pack('<HH',a,b)


def address_pairs(source,seg):
    md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
    md.detail=True;md.skipdata=True
    # Module info starts here; the remainder of seg0 is rodata, not code.
    limit=min(seg['size'],0xcab28)
    pending={};pairs=[]
    for n,i in enumerate(md.disasm(source[seg['off']:seg['off']+limit],seg['va'])):
        if i.id==0:pending.clear();continue
        m=re.fullmatch(r'(\w+), #(0x[0-9a-f]+|[0-9]+)',i.op_str)
        reg=i.operands[0].reg if i.operands and i.operands[0].type==capstone.arm.ARM_OP_REG else None
        if i.mnemonic=='movw' and m:
            pending[reg]=(n,i.address,int(m[2],0))
        elif i.mnemonic=='movt' and m and reg in pending:
            prev,at,low=pending.pop(reg)
            if n-prev<24:pairs.append((low|int(m[2],0)<<16,at,i.address))
        else:
            _,writes=i.regs_access()
            for r in writes:pending.pop(r,None)
    return pairs
