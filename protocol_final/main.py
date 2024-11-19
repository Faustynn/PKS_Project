import threading
from blackBox import getIpAddress
from sendThread import sendPacket
from receiveThread import receivePacket
from controlThread import sendControlPacket

# ERR handling,view checksum in text+file
# ERR handling if fragment dont resive
# send all types file
# check keep alive


if __name__ == "__main__":
    targetIp = input("Enter the target IP: ")
    if targetIp.count('.') != 3:
        targetIp = getIpAddress()
        print(f"set the IP to the IP of local host ({targetIp})")
    targetPort = int(input("Enter the target port: "))
    listenPort = int(input("Enter the port to listen on: "))

    sendThread = threading.Thread(target=sendPacket, args=(targetIp, targetPort))
    controlThread = threading.Thread(target=sendControlPacket, args=(targetIp, targetPort))
    receiveThread = threading.Thread(target=receivePacket, args=(targetIp, listenPort, targetPort))

    receiveThread.start()
    sendThread.start()
    controlThread.start()