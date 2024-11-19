-- Def. protocol
my_protocol = Proto("Protocol_UDP", "Custom")

-- Def. fields
local f_msgType = ProtoField.uint8("my_protocol.msgType", "Mess. Type", base.DEC, nil, 0xF0)
local f_flags = ProtoField.uint8("my_protocol.flags", "Flags", base.DEC, nil, 0x0F)
local f_fragmentSeq = ProtoField.uint16("my_protocol.fragmentSeq", "Fragment Sequence", base.DEC)
local f_timestamp = ProtoField.uint8("my_protocol.timestamp", "Timestamp", base.DEC)
local f_payload = ProtoField.bytes("my_protocol.payload", "Data")
local f_checksum = ProtoField.uint16("my_protocol.checksum", "Checksum", base.HEX)

-- Create fields into protocol
my_protocol.fields = {f_msgType, f_flags, f_fragmentSeq, f_timestamp, f_payload, f_checksum}

-- Dissector
function my_protocol.dissector(buffer, pinfo, tree)
    pinfo.cols.protocol = my_protocol.name

    local subtree = tree:add(my_protocol, buffer(), "MeredovN Protocol")

    subtree:add(f_msgType, buffer(0, 1))
    subtree:add(f_flags, buffer(0, 1))
    subtree:add(f_fragmentSeq, buffer(1, 2))
    subtree:add(f_checksum, buffer(3, 2))
    subtree:add(f_timestamp, buffer(5, 1))
    subtree:add(f_payload, buffer(6, buffer:len() - 6))
end

-- Port specification
local udp_port = DissectorTable.get("udp.port")
udp_port:add(3322, my_protocol)
udp_port:add(2233, my_protocol)