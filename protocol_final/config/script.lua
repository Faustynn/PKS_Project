-- MeredovN Custom UDP Protocol
local mcup = Proto("MCUP", "Meredov Custom UDP Protocol (MCUP)")

-- Comprehensive Message Type Definitions
local msg_types = {
    [1] = "Control Packet",
    [2] = "Single Message Packet",
    [3] = "Multi-Fragment Message Packet",
    [4] = "File Transfer Packet",
    [5] = "ACK/NACK Packet"
}

-- Detailed Flag Definitions
local flag_definitions = {
    -- Control Packet Flags
    [1] = {
        [2] = "SYN",
        [3] = "SYN-ACK",

        [4] = "KEEP_ALIVE",
        [5] = "KEEP_ALIVE-ACK",

        [8] = "FIN",
        [9] = "FIN-ACK"
    },

    -- Single Message Packet Flags
    [2] = {
        [1] = "Single Message",

        [5] = "All Fragments Send"
    },
    -- Multi-Fragment Message Packet Flags
    [3] = {
        [2] = "Fragments size Transfer",
        [4] = "Fragment Message"
    },
    -- File Transfer Packet Flags
    [4] = {
        [1] = "Filename Transfer",
        [2] = "File Size Transfer",
        [3] = "Fragment Count Transfer",
        [4] = "File Fragment part",

        [6] = "Look missing fragment"
    },

    -- ACK/NACK Packet Flags
    [5] = {
        [1] = "ACK",
        [2] = "NACK"
    }
}

-- Protocol Fields
local f_msgType_flags = ProtoField.uint8("mcup.msgType_flags", "Message Type and Flags", base.HEX)
local f_checksum = ProtoField.uint16("mcup.checksum", "Checksum", base.HEX)
local f_fragmentSeq = ProtoField.uint16("mcup.fragmentSeq", "Fragment Sequence", base.DEC)
local f_timestamp = ProtoField.uint8("mcup.timestamp", "Timestamp", base.DEC)
local f_payload = ProtoField.bytes("mcup.payload", "Payload")
local f_detailed_type = ProtoField.string("mcup.detailed_type", "Detailed Type")

-- Register protocol fields
mcup.fields = {
    f_msgType_flags,
    f_checksum,
    f_fragmentSeq,
    f_timestamp,
    f_payload,
    f_detailed_type
}

-- Main dissector function
function mcup.dissector(buffer, pinfo, tree)
    -- Validate buffer size (minimum 6 bytes)
    if buffer:len() < 6 then
        return
    end

    -- Set protocol column
    pinfo.cols.protocol = mcup.name

    -- Create protocol subtree
    local subtree = tree:add(mcup, buffer(), "MCUP Protocol")

    -- Parse first byte (message type and flags)
    local msgType_flags = buffer(0, 1):uint()
    local msgType = bit.rshift(msgType_flags, 4)
    local flags = bit.band(msgType_flags, 0x0F)
    subtree:add(f_msgType_flags, buffer(0, 1), msgType_flags)

    -- Add checksum
    local checksum = buffer(1, 2):uint()
    subtree:add(f_checksum, buffer(1, 2), checksum)

    -- Add fragment sequence
    local fragmentSeq = buffer(3, 2):uint()
    subtree:add(f_fragmentSeq, buffer(3, 2), fragmentSeq)

    -- Add timestamp
    local timestamp = buffer(5, 1):uint()
    subtree:add(f_timestamp, buffer(5, 1), timestamp)


    -- Determine detailed packet type
    local detailed_type = "Unknown"
    if flag_definitions[msgType] and flag_definitions[msgType][flags] then
        detailed_type = flag_definitions[msgType][flags]
    end
    subtree:add(f_detailed_type, buffer(), detailed_type)

    -- Add payload if exists
    if buffer:len() > 6 then
        subtree:add(f_payload, buffer(6, buffer:len() - 6))
    end

    -- Update info column
    pinfo.cols.info = string.format("%s (%s), Seq: %d, Flags: 0x%x",
        msg_types[msgType] or "Unknown",
        detailed_type,
        fragmentSeq,
        flags)
end

-- Register for UDP ports
local udp_port = DissectorTable.get("udp.port")
udp_port:add(3322, mcup)  -- Primary port
udp_port:add(2233, mcup)  -- Secondary port