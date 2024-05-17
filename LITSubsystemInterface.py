import typing
import threading
import pickle
import socket
from utils import find_missing_numbers_as_ranges_tuples, is_overlap, SystemLEDData
import itertools
from ObjectDetectionModel import ObjectDetectionModel
import sys



class LITSubsystemData():
    """A data structure used to store information relevant between the GUI, ObjectDetectionModel used for performing Object Detection on the camera specified, and the potential server the user 
    would like data sent to for addressing the LED subsystems."""
    def __init__(self, camera_idx: int, object_detection_model: typing.Union[ObjectDetectionModel, None] = None, number_of_leds: int = 256,
                 number_of_sections: int = 8, host: str = None, port: int = None, image_preview_height: int = 405, image_preview_width:int = 720) -> None:
        """
        Parameters:
        - camera_idx (int): The USB ID number for the camera of this Subsystem. This is how the device is identified by the OS.
        - object_detection_model (typing.Union[ObjectDetectionModel, None]): The detection model used to perform inference on the camera_idx.
        - number_of_leds (int): The number of LEDs of the LED Subsystem.
        - number_of_sections (int): When specifying how the lights would like to be sectionalzied when attempting to illuminate an object, this value is used to divide the LED Subsystem
                                    into an equal number of sections equal to number_of_sections. The larger this number the smalled the column illuminated when an object is detected.
        - host (str): The Server IP Address where information will be sent, involving LEDs to Illumuniate.     
        - port (int): The specific port you would like to create your connectiom to the server with. 
        """
        self.camera_idx = camera_idx
        self.object_detection_model = object_detection_model

        self.number_of_leds = number_of_leds
        self.number_of_sections = number_of_sections
        self.host = host
        self.port = port
        self.system_led_data = SystemLEDData(None, None)
        self.manual_status: bool = False
        self.auto_status: bool = False
        self.force_all_leds_on: bool = False 
        self.attempt_to_create_client_conn()
        if isinstance(self.object_detection_model, ObjectDetectionModel):
            self.set_object_detection_model(self.object_detection_model)
        else:
            self.image_preview_height = image_preview_height
            self.image_preview_width = image_preview_width
        return
    
    def set_object_detection_model(self, object_detection_model: ObjectDetectionModel):
        if isinstance(object_detection_model, ObjectDetectionModel):
            self.object_detection_model = object_detection_model
            self.object_detection_model.set_send_data_callback(self.send_data_for_led_addressing)
            self.object_detection_model.set_led_ranges_for_objects(number_of_leds=self.number_of_leds, number_of_sections=self.number_of_sections)
            self.object_detection_model.system_led_data = self.system_led_data
            self.image_preview_width = self.object_detection_model.resolution[0]
            self.image_preview_height = self.object_detection_model.resolution[1]    
            if self.client_conn:
                self.object_detection_model.client_conn = self.client_conn    
                self.object_detection_model.thread_lock = self.send_lock  
            else:
                self.object_detection_model.client_conn = False   
                self.object_detection_model.thread_lock = False  
        return
    
    def attempt_to_create_client_conn(self):
        """Called in the constructor, used to create a connection to the server if provided a host and port. This connection is unique to each instance, as well as the lock creatred when connecting.
        This connection and thread lock is also passed to the object detection model if provide in the constructor. If the server and port are not present, the client_conn and send_lock
        attributes are set to False."""

        if self.host and self.port:
            # try:
                self.send_lock = threading.Lock()
                self.client_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_conn.connect((self.host,self.port))
                if self.object_detection_model:
                    self.object_detection_model.set_client_conn(self.client_conn)
                    self.object_detection_model.set_thread_lock(self.send_lock)
                return
            # except:
                pass
        self.client_conn = False
        self.send_lock = False
        return

    def send_data_for_led_addressing(self, manual_event: bool)->None:
        """Sends data to the respective LED subsystem associated with the instance of this ObjectDetectionModel using a socket connection. This is used to update the state of LEDs throughout the subsystem.
        The reason for the manual event argument is so that we don't continously address manual LEDs, as they only change on manual LED events. This saves time addressing LEDs.
        
        Parameters:
        - manual_event (bool): A boolean indicating if this method was called a part of a manual control event in the GUI, or an ObjectDetectionModel sending led data."""
 
        #FORCING ALL LEDS ON OVERRIDES ALL OF SETTINGS
        if self.force_all_leds_on and self.manual_status:
            data = [0, [(0,self.number_of_leds)], 1, []]


        elif self.auto_status or self.manual_status:
            self.system_led_data.update_led_data_for_sending(self.auto_status, self.manual_status, self.number_of_leds)                    
            if manual_event:
                data = [0, self.system_led_data.full_manual_list, self.system_led_data.manual_led_data.brightness, self.system_led_data.turn_off_leds.manual_led_tuple_list]
            elif self.system_led_data.auto_led_data_list and self.auto_status:
                data = [1, [(auto_led.led_range, auto_led.brightness) for auto_led in self.system_led_data.auto_led_data_list], self.system_led_data.turn_off_leds.manual_led_tuple_list]
            elif self.manual_status:
                try:
                    if self.system_led_data.full_manual_list:
                        data = [0, self.system_led_data.full_manual_list, self.system_led_data.manual_led_data.brightness, self.system_led_data.turn_off_leds.manual_led_tuple_list]
                    else:
                        data = [0, [], 0, [(0,self.number_of_leds)]]
                except:
                        data = [0, [], 0, [(0,self.number_of_leds)]]
            else:
                data = [0, [], 0, [(0,self.number_of_leds)]]
        else:
            data = [0, [], 0, [(0,self.number_of_leds)]]

        
        pickle_data = pickle.dumps(data)
        if self.send_lock:
            with self.send_lock:
                self.client_conn.send(pickle_data)
        elif self.client_conn:
            self.client_conn.send(pickle_data)      
        return
    

