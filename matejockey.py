#!/usr/bin/env python2.7

# Hello!
# This is matelight-jockey 0.1 or something.
# It is based on coon's ingenius simple matetv tool.
# (which you can find @ https://github.com/c-base/matetv )
#
# See LICENSE and README.md for more information, for now.
# (Inline docs etc. will follow - this is still a hack)

from PyQt4 import QtCore, QtGui, Qt, QtNetwork
from PyQt4.QtGui import QApplication, QLineEdit, QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QFileDialog
# from gui import Ui_Form

import struct
import time
import sys
import cv
import socket

import os

import pygame
import pygame.midi
from pygame.locals import *

from Axon.Component import component
from Axon.Ipc import shutdownMicroprocess
from Axon.Scheduler import scheduler

from Kamaelia.Chassis.Pipeline import Pipeline


IP = "matelight.cbrp3.c-base.org"
PORT = 1337
RESX = 40
RESY = 16
KAMERA_NR = 0
TOTAL_PIXELS = RESX * RESY
FRAMES_PER_SECOND = 50
TIME_BETWEEN_FRAMES = 1.0 / FRAMES_PER_SECOND

screennames = ['bitwiglogo.png', '1up.png', 'text-B.png', 'text-bit.png', 'text-wig.png', 'rauschen.png']
screens = {}


class ImageRepository(component):
    def __init__(self, images=[]):
        super(ImageRepository, self).__init__()

        self.images = {}

        if len(images) > 0:
            for no, item in enumerate(images):
                self.images[no] = cv.LoadImage(os.path.abspath("./" + item))


    def finished(self):
        while self.dataReady("control"):
            msg = self.recv("control")
            if type(msg) in (shutdownMicroprocess):
                self.send(msg, "signal")
                return True
        return False


    def main(self):
        while not self.finished():

            while not self.anyReady():
                self.pause()
                yield 1

            while self.dataReady("inbox"):
                no = int(self.recv("inbox"))
                self.send(self.images[no], "outbox")

            yield 1


class MidiInput(component):
    def __init__(self, device_id=None):
        super(MidiInput, self).__init__()

        pygame.midi.init()

        self.midi_print_device_info()

        if not device_id:
            self.midi_device = pygame.midi.get_default_input_id()
        else:
            self.midi_device = device_id

        try:
            self.midi = pygame.midi.Input(self.midi_device, 0)
        except Exception as e:
            print("ERR: Could not open midi input device %s" % self.midi_device)
            print("ERR: Exception ", e)
            sys.exit()

        print "INFO: Opened midi input device %s" % self.midi_device
        self.midi_print_device_info()

    def midi_print_device_info(self):
        for i in range(pygame.midi.get_count()):
            r = pygame.midi.get_device_info(i)
            (interf, name, inputs, outputs, opened) = r

            in_out = ""
            if inputs:
                in_out = "(input)"
            if outputs:
                in_out = "(output)"

            print ("%2i: interface :%s:, name :%s:, opened :%s:  %s" %
                   (i, interf, name, opened, in_out))

    def finished(self):
        while self.dataReady("control"):
            msg = self.recv("control")
            if type(msg) in (shutdownMicroprocess):
                self.send(msg, "signal")
                return True
        return False


    def main(self):
        while not self.finished():
            if self.midi.poll():
                while self.midi.poll():
                    print("Received midi data!")
                    mididata = self.midi.read(1)

                    self.send(mididata, "outbox")
                    yield 1

            yield 1


class CVCamera(component):
    def __init__(self, device_id=0):
        super(CVCamera, self).__init__()
        self.cam = cv.CaptureFromCAM(device_id)


    def finished(self):
        while self.dataReady("control"):
            msg = self.recv("control")
            if type(msg) in (shutdownMicroprocess):
                self.send(msg, "signal")
                return True
        return False


    def main(self):
        while not self.finished():
            frame = cv.QueryFrame(self.cam)
            if not frame:
                print("Oh, no camera attached! Change this and rerun!")
                sys.exit()

            mlframe = cv.CreateImage((40, 16), cv.IPL_DEPTH_8U, frame.channels)
            gr = frame[128: 384, 0: 640]  # Crop from x, y, w, h -> 100, 200, 100, 200

            cv.Resize(gr, mlframe)
            self.send(mlframe, "outbox")

            yield 1


class Matelight(component):
    def __init__(self, address='127.0.0.1', port=1337):
        super(Matelight, self).__init__()
        self.address = address
        self.port = port


    def finished(self):
        while self.dataReady("control"):
            msg = self.recv("control")
            if type(msg) in (shutdownMicroprocess):
                self.send(msg, "signal")
                return True
        return False

    def cmd_send_image(self, image, brightness, gamma):
        ml_data = image + "\00\00\00\00"
        data_c = bytearray([int(((x / 255.0) ** (gamma / 100.0)) * 255 * (brightness / 100.0)) for x in list(ml_data)])
        try:

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data_c, (self.address, self.port))
        except Exception as e:
            print("Meeeh: ", e)

    def main(self):
        while not self.finished():

            while not self.anyReady():
                self.pause()
                yield 1

            while self.dataReady("inbox"):
                frame = self.recv("inbox")

                self.cmd_send_image(frame, 100, 100)

            yield 1


class ColorFilter(component):
    Inboxes = {'inbox': "Image input",
               'control': "Control input",
               'color': "RGB percentage (0-100) tuple: (r,g,b)"}

    def __init__(self, color=(100, 100, 100)):
        super(ColorFilter, self).__init__()
        self.color = color

    def finished(self):
        while self.dataReady("control"):
            msg = self.recv("control")
            if type(msg) in (shutdownMicroprocess):
                self.send(msg, "signal")
                return True
        return False


    def main(self):
        while not self.finished():
            while not self.anyReady():
                self.pause()
                yield 1

            while self.dataReady("color"):
                # Hmm, maybe only get the last message and clear the queue? Could be faster
                self.color = self.recv("color")

            while self.dataReady("inbox"):
                frame = self.recv("inbox")
                mat = cv.GetMat(frame)
                bitstring = []

                for row in xrange(mat.rows):
                    for column in xrange(mat.cols):
                        red = int(mat[row, column][2] * self.color[0] / 100.0)
                        green = int(mat[row, column][1] * self.color[1] / 100.0)
                        blue = int(mat[row, column][0] * self.color[2] / 100.0)
                        bitstring.extend(struct.pack('BBB', red, green, blue))

                self.send(bytearray(bitstring), "outbox")

            yield 1


class MyForm(QtGui.QMainWindow):
    def __init__(self, parent=None, device_id=None):

        pygame.init()

        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        QtCore.QObject.connect(self.ui.pushButton_stream_webcam, QtCore.SIGNAL("clicked()"), self.cmd_stream_webcam)
        QtCore.QObject.connect(self.ui.horizontalSlider_fps, QtCore.SIGNAL("valueChanged(int)"), self.cmd_fps_changed)
        QtCore.QObject.connect(self.ui.verticalSlider_red, QtCore.SIGNAL("valueChanged(int)"),
                               self.cmd_red_slider_changed)
        QtCore.QObject.connect(self.ui.verticalSlider_green, QtCore.SIGNAL("valueChanged(int)"),
                               self.cmd_green_slider_changed)
        QtCore.QObject.connect(self.ui.verticalSlider_blue, QtCore.SIGNAL("valueChanged(int)"),
                               self.cmd_blue_slider_changed)
        QtCore.QObject.connect(self.ui.verticalSlider_gamma, QtCore.SIGNAL("valueChanged(int)"),
                               self.cmd_gamma_slider_changed)
        QtCore.QObject.connect(self.ui.verticalSlider_brightness, QtCore.SIGNAL("valueChanged(int)"),
                               self.cmd_brightness_slider_changed)


        # Network init
        self.sock = QtNetwork.QUdpSocket()
        self.sock.bind(QtNetwork.QHostAddress.Any, PORT)
        self.connect(self.sock, QtCore.SIGNAL("readyRead()"), self.on_recv_udp_packet)

        self.image = None
        self.streaming = False
        self.threshold = 128
        self.equalize = False
        self.fps = FRAMES_PER_SECOND
        self.time_between_frames = TIME_BETWEEN_FRAMES

        self.max_red = 100
        self.max_green = 100
        self.max_blue = 100
        self.max_gamma = 100
        self.max_brightness = 100


    def cv_resize_and_grayscale(self, input_image, threshold, doEqualize):
        image = cv.CreateImage((input_image.width, input_image.height), 8, 1)
        cv.CvtColor(input_image, image, cv.CV_BGR2GRAY)

        if doEqualize:
            cv.EqualizeHist(image, image)  # equalize the pixel brightness
        cv.Threshold(image, image, threshold, 255, cv.CV_THRESH_OTSU)  # convert to black / white image

        image_resized = cv.CreateImage((RESX, RESY), image.depth, image.channels)  # resize to fit into r0ket display
        cv.Resize(image, image_resized, cv.CV_INTER_NN)

        return image_resized


    # GUI events
    def cmd_load_image(self):
        file_path = str(self.ui.lineEdit_file_path.text())
        self.image = self.cv_load_image(file_path)
        print "image loaded!"

    def cmd_stream_webcam(self):
        end_time = 0
        counter = 1
        screenactive = 0

        while True:

            c = cv.WaitKey(2)

            if c == 27:  # esc
                return

            g = cv.CreateImage(cv.GetSize(frame), cv.IPL_DEPTH_8U, frame.channels)
            gr = frame[128: 384, 0: 640]  # Crop from x, y, w, h -> 100, 200, 100, 200
            ml = cv.CreateImage((40, 16), cv.IPL_DEPTH_8U, frame.channels)
            cv.Resize(gr, ml)
            cv.ShowImage("Matelight TV", gr)

            mididata = False
            if 0:
                if mididata:
                    if mididata[0][0][0] == 176:
                        value = mididata[0][0][2]
                        channel = mididata[0][0][1]
                        if value >= 100:
                            value = 100
                        if channel == 2:
                            self.max_red = value
                        elif channel == 3:
                            self.max_green = value
                        elif channel == 5:
                            self.max_blue = value
                    screennumber = mididata[0][0][1] - 60
                    if mididata[0][0][0] == 144:
                        print("MIDI Notedown received: ", screennumber)
                        screenactive = screennumber
                    elif mididata[0][0][0] == 128:
                        print("MIDI Noteup received: ", screennumber)
                        screenactive = -1
                    else:
                        print(mididata)

            if c >= 49 and c <= 59:
                if screenactive == c - 49:
                    screenactive = -1
                else:
                    screenactive = c - 49

            if screenactive in screens:
                ol = cv.CreateImage((40, 16), cv.IPL_DEPTH_8U, frame.channels)
                cv.Add(ml, screens[screenactive], ol)
                ml = ol
            c = 0

            if time.time() > end_time:
                end_time = time.time() + self.time_between_frames
                # self.cmd_send_image(ml, 0.25, 2)
                self.cmd_send_image(ml, self.max_brightness, self.max_gamma)

            counter += 1

    def cmd_send_image(self, image, brightness, gamma):
        mg_mat = cv.GetMat(image)
        ml_data = self.convert_img_matrix_to_matelight(mg_mat) + "\00\00\00\00"
        data_c = bytearray([int(((x / 255.0) ** (gamma / 100.0)) * 255 * (brightness / 100.0)) for x in list(ml_data)])
        try:

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data_c, (IP, PORT))
        except Exception as e:
            print("Meeeh: ", e)

    def cmd_fps_changed(self, value):
        self.fps = value
        self.time_between_frames = 1.0 / self.fps

    def cmd_red_slider_changed(self, value):
        self.max_red = value
        print "red slider changed to %d %%" % value

    def cmd_green_slider_changed(self, value):
        self.max_green = value
        print "green slider changed to %d %%" % value

    def cmd_blue_slider_changed(self, value):
        self.max_blue = value
        print "blue slider changed to %d %%" % value

    def cmd_gamma_slider_changed(self, value):
        self.max_gamma = value
        print "gamma slider changed to %d %%" % value

    def cmd_brightness_slider_changed(self, value):
        self.max_brightness = value
        print "brightness slider changed to %d %%" % value


    def cmd_equalize_changed(self, state):
        self.equalize = state
        print state

    def cmd_browse_file(self):
        self.ui.lineEdit_file_path.setText(QFileDialog.getOpenFileName())

    def send_udp_packet(self, payload):
        try:
            self.sock.writeDatagram(payload, QtNetwork.QHostAddress(IP), PORT)
        except Exception as e:
            print("Whuuuiii:", e)


    def on_recv_udp_packet(self):
        print "UDP packet received but ignored. TODO: implement handler."


def main():
    # app = QtGui.QApplication(sys.argv)
    #myapp = MyForm(device_id=3)
    #myapp.show()
    #sys.exit(app.exec_())

    Pipe = Pipeline(CVCamera(),
                    ColorFilter(color=(0, 100, 0)),
                    Matelight()
    ).activate()

    scheduler.run.runThreads()


if __name__ == "__main__":
    main()
