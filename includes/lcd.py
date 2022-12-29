import usb
import usb.backend.libusb1
import codecs
from datetime import datetime, timedelta
from math import ceil
from time import sleep
from threading import Thread
from os import sys

class LCD:
    def __init__(self):
        self.__vendor_id = 0x1b1c
        self.__product_id = 0x0c39
        self.__device = usb.core.find(idVendor=self.__vendor_id, idProduct=self.__product_id)

        if self.__device is None:
            raise ValueError("LCD not found!")

        self.__device.set_configuration()

        self.__config = self.__device.get_active_configuration()
        self.__interface = self.__config[(0, 0)]
        self.__endpoint = usb.util.find_descriptor(self.__interface, custom_match=lambda e: usb.util.endpoint_direction(
            e.bEndpointAddress) == usb.util.ENDPOINT_OUT)

        if self.__endpoint is None:
            raise ValueError("LCD out endpoint not found!")

        self.__last_time = datetime.now()
        self.__max_fps = 25
        self.__frametime_ms = 1000 / self.__max_fps
        
        self.__thread = None ## anytime this class is doing something in the background, this flag will be there
        self.__is_thread = False

        print("Config:\n", self.__endpoint, "\nFrametime: ", self.__frametime_ms)

    def __send_packet(self, data_length, data, packets_sent, signature):
        packet = b"".join([b"\x02", b"\x05", b"\x40", signature, packets_sent.to_bytes(1, byteorder="big"), b"\x00", (data_length >> 8 & 0xFF).to_bytes(1, byteorder="big"), (data_length & 0xFF).to_bytes(1, byteorder="big"), data])
        if len(packet)<1024:
            packet += b"\x00"*(1024-len(packet))
        self.__endpoint.write(packet)

    def send_packet_raw(self, data):
        self.__endpoint.write(data)

    def __send_static_image(self, image_path):
        while True:
            if not self.__is_thread:
                return
            loop_start=datetime.now()
            if datetime.now() - self.__last_time < timedelta(milliseconds=1000):
                # making sure we dont get weird glitches by bombarding the display with jpegs
                continue
            self.__last_time = datetime.now()
            image = ""
            with open(image_path, "rb") as f:
                image = f.read().hex()
            packets_sent = 0
            packets_to_be_sent = [image[i:i+1016*2] for i in range(0, len(image), 1016*2)]
            for i in packets_to_be_sent:
                if len(i) < 1016:
                    self.__send_packet(len(i), bytes.fromhex(i), packets_sent, b"\x01")
                else:
                    self.__send_packet(len(i), bytes.fromhex(i), packets_sent, b"\x00")
                packets_sent += 1
            timediff = datetime.now() - loop_start
            if timediff < timedelta(milliseconds=1000):
                sleep((timedelta(milliseconds=1000) - timediff).total_seconds()) # waiting for next frame moment in case we rendered prematurely
            
    def send_static_image(self, image_path: str):
        """
        This is a method that shows a static JPEG on the LCD until terminated. It does so by threading. The method LCD.stop_displaying() provides a way to terminate this. It sends the image at 1fps irrespective of the current fps setting.
        Args:
            image_path (str): Path to the image. Needs to be a square JPEG. Max resolution is 480x480.
        """
        self.__is_thread = True
        self.__thread = Thread(target=self.__send_static_image, args=(image_path,))
        self.__thread.start()
    
    def stop_displaying(self):
        self.__is_thread = False
        
    def send_frame(self, image: str):
        """
        This is a method used by themes to render frames directly to the display. It sends only a single frame without any control save for limiting the fps to the user-se value. It's intended to be used by themes/other scripts.
        
        Args:
            image (str): Image as a hex string.
        """
        if datetime.now() - self.__last_time < timedelta(milliseconds=self.__frametime_ms):
            # making sure we dont get weird glitches by bombarding the display with jpegs
            return
        self.__last_time = datetime.now()
        packets_sent = 0
        packets_to_be_sent = [image[i:i+1016*2] for i in range(0, len(image), 1016*2)]
        for i in packets_to_be_sent:
            if len(i) < 1016:
                self.__send_packet(len(i), bytes.fromhex(i), packets_sent, b"\x01")
            else:
                self.__send_packet(len(i), bytes.fromhex(i), packets_sent, b"\x00")
            packets_sent += 1
            
    def get_framerate(self) -> float:
        """
        Getter for set framerate.
        Returns:
            float: Framerate in fps
        """
        return self.__max_fps
    
    def get_frametime(self) -> float:
        """
        Getter for frametime.
        Returns:
            float: Frametime in ms.
        """
        return self.__frametime_ms
    
    def set_framerate(self, fps: float):
        """
        Setter for framerate.
        Args:
            fps (float)

        Raises:
            TypeError: FPS needs to be a float.
            ValueError: FPS should be 30 or less/1 or more.
        """
        if type(fps) != float:
            raise TypeError("Please only use floats for FPS.")
        if fps > 30 or fps < 1:
            raise ValueError("FPS shouldn't be more than 30 and should be more than 1.")
        self.__max_fps = fps
        self.__frametime_ms = 1000/fps
            


if __name__ == "__main__":
    # Example usage
    lcd = LCD()
    lcd.send_static_image("1.jpeg")
    sleep(5)
    lcd.stop_displaying()
