"""
Where solution code to HW5 should be written.  No other files should
be modified.
"""

import signal
import select
import socket
import io
import time
import struct
import homework5
import homework5.logging


def update_frame(pipe, seq_num, slot):
    count = seq_num
    for key, value in pipe.items():
        if key == seq_num:
            if value[0] == 'ACK':
                value[0] = 'SYN'
                seq_num += 1
                slot += 1
        else:
            while pipe.get(count, None) is not None:
                value = pipe[count]
                if value[0] == 'SYN':
                    pipe.pop(count)
                count += 1
            break
    return seq_num, slot


def sendagain(pipe, find_packet, TimeoutInterval):
    for key, value in pipe.items():
        if value[0] == 'NAK':
            current_time = time.time()
            if current_time - value[1] > TimeoutInterval:
                value[1] = current_time
                sock.send(find_packet[key])
                sock.settimeout(TimeInterval)


def send(sock: socket.socket, data: bytes):
    """
    Implementation of the sending logic for sending data over a slow,
    lossy, constrained network.
    Args:
        sock -- A socket object, constructed and initialized to communicate
                over a simulated lossy network.
        data -- A bytes object, containing the data to send over the network.
    """
    logger = homework5.logging.get_logger("hw5-sender")
    TimeoutInterval = 1
    SampleRTT = 0
    EstimatedRTT = 0
    DevRTT = 0.0
    slot = 0
    w_frame = 6
    p_seq_num = 0
    seq_num = 0
    new_seq = 0
    chunks = 0
    pipe = dict()
    find_packet = []
    chunk_size = homework5.MAX_PACKET - 4
    offsets = range(0, len(data), chunk_size)

    for chunk in [data[i:i + chunk_size] for i in offsets]:
        header = struct.pack('I', seq_num)
        full_packet = header + chunk
        find_packet.append(full_packet)
        seq_num += 1
        chunks += 1
    seq_num = 0

    while slot + w_frame <= chunks:
        while p_seq_num < slot + w_frame:
            start = time.time()
            sock.send(find_packet[p_seq_num])
            pipe[p_seq_num] = ['NAK', start]
            p_seq_num += 1

        while new_seq < p_seq_num:
            try:
                new_data = sock.recv(homework5.MAX_PACKET)
                if not new_data:
                    break

                SampleRTT = time.time() - start
                EstimatedRTT = (0.875 * EstimatedRTT) + (0.125 * SampleRTT)
                DevRTT = (0.75 * DevRTT)
                DevRTT += (0.25 * abs(SampleRTT - EstimatedRTT))
                TimeoutInterval = EstimatedRTT + (4 * DevRTT)
                new_seq = struct.unpack('I', new_data[:4])[0]
                got = pipe.get(new_seq)

                if got:
                    pipe[new_seq] = ['ACK', pipe[new_seq][1]]

                if new_seq == seq_num:
                    seq_num, slot = update_frame(pipe, seq_num, slot)
                    break
            except socket.timeout:
                sendagain(pipe, find_packet, TimeoutInterval)
                continue


def recv(sock: socket.socket, dest: io.BufferedIOBase) -> int:
    """
    Implementation of the receiving logic for receiving data over a slow,
    lossy, constrained network.
    Args:
        sock -- A socket object, constructed and initialized to communicate
                over a simulated lossy network.
    Return:
        The number of bytes written to the destination.
    """
    logger = homework5.logging.get_logger("hw5-receiver")

    num_bytes = 0
    seq_num = 0

    priority_list = dict()

    while True:
        data = sock.recv(homework5.MAX_PACKET)
        if not data:
            break

        header = struct.unpack('I', data[:4])[0]
        headless_data = data[4:]
        sock.send(struct.pack('I', header))

        priority_list[header] = headless_data

        if header == seq_num:
            while True:
                try:
                    data = priority_list[seq_num]
                    dest.write(data)
                    num_bytes += len(data)
                    dest.flush()
                    seq_num += 1
                except KeyError:
                    break
        priority_list.clear()

    return num_bytes
