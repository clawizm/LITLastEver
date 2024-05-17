import threading
from threading import Thread
import cv2
from queue import Queue
import numpy as np
import time
import pickle
import socket
import PySimpleGUI as sg    
from utils import AutoLEDData
from tensorflow.lite.python.interpreter import Interpreter 
from tensorflow.lite.python.interpreter import load_delegate
import csv

import typing
from multiprocessing import Process, Queue
import math
import mediapipe as mp
import copy
import itertools

def pre_process_landmark(landmark_list):
    temp_landmark_list = copy.deepcopy(landmark_list)

    # Convert to relative coordinates
    base_x, base_y = 0, 0
    for index, landmark_point in enumerate(temp_landmark_list):
        if index == 0:
            base_x, base_y = landmark_point[0], landmark_point[1]

        temp_landmark_list[index][0] = temp_landmark_list[index][0] - base_x
        temp_landmark_list[index][1] = temp_landmark_list[index][1] - base_y

    # Convert to a one-dimensional list
    temp_landmark_list = list(
        itertools.chain.from_iterable(temp_landmark_list))

    # Normalization
    max_value = max(list(map(abs, temp_landmark_list)))

    def normalize_(n):
        return n / max_value

    temp_landmark_list = list(map(normalize_, temp_landmark_list))

    return temp_landmark_list

def calc_landmark_list(image, landmarks):
    image_width, image_height = image.shape[1], image.shape[0]

    landmark_point = []

    # Keypoint
    for _, landmark in enumerate(landmarks.landmark):
        landmark_x = min(int(landmark.x * image_width), image_width - 1)
        landmark_y = min(int(landmark.y * image_height), image_height - 1)
        # landmark_z = landmark.z

        landmark_point.append([landmark_x, landmark_y])

    return landmark_point

def focal_length_finder(camera_video_width: int, horizontal_fov: int)->float:
    """Using the width of the video from the camera in pixels and the horizontal field of view of the camera, both in pixels, this functuion returns the focal length in pixels of the camera.
    
    Parameters:
    - camera_video_width (int): The width of the camera image in pixels.
    - horizontal_fov (int): The cameras horizontal field of view in degrees."""

    fov_rad = math.radians(horizontal_fov)
    return camera_video_width / (2 * math.tan(fov_rad / 2))

def create_fov_range_list(hfov: int, num_of_sections: int)->typing.Union[list[float], list[int]]:
    """Returns a list of float or integer values equally spaced apart by setting the hfov arguement into 2 seperate values, which are the the positive and negative states of the number divided by two.
    Then these two numbers are used to create a list of size 'num_of_sections' where the number at index 0 is the negative state and the number at the last index is the positive state. All numbers in the equal distance apart,
    by an amount equal to hfov / num_of_sections.
    
    Parameters:
    - hfov (int): The horizontal field of view of a camera.
    - num_of_sections (int): The desired length of the list containing equally spaced numbers ranging from the negative value of hfov/2 to the postive value of hfov/2."""

    max_positive_fov = round(hfov / 2)
    max_negative_fov = -1 * max_positive_fov
    lst = [max_negative_fov + x * (max_positive_fov - max_negative_fov) / num_of_sections for x in range(num_of_sections + 1)]
    lst.sort(reverse=True)
    return lst

def create_led_tuple_range_list(number_of_leds: int, num_of_sections: int)->list[tuple[int, int]]:
    """Returns a list of tuples containing the start and stopping point of LED ranges based on the number of LEDs of the subsystem specified divided by the number of sections the user would 
    like the subsystem divided into.
    
    Parameters:
    - number_of_leds (int): The number of LEDs used in a panel. If two panels are used horizontally, the double the amount of LEDs.
    - num_of_sections (int): The amount of equally spaced ranges you would like to split the number of LEDs into.
    """

    led_tuples_list = []
    leds_ranges = round(number_of_leds/num_of_sections)
    i = 0
    while i < number_of_leds:
        led_tuples_list.append((i, i+leds_ranges))
        i += leds_ranges
    return led_tuples_list

def brightness_based_on_distance(distance: float, min_distance: float=0.01, max_distance: float=5.0, linear_slope:float =0.25, exponential_base:typing.Union[float, int]=2)->float:
    """Using a distance in terms of meters, this returns a brightness value between 0-1. This is done by comparing the distance provided against the preset (adjustable) parameters.
    If the distance is greater than the threshold set, which is half of the max distance, the brighness will be calculated as an expoential, such that changes in brightness are more drastic the closer the provided distance
    is to the max distance. If the distance is less than the threshold, the brightness will be calulated as a function of a linear slope.
    
    Parameters:
    - distance (float): The distance of object/location away from lights.
    - min_distance (float): The minimum distance a distance provided can be that won't result in a value of 0 (No Brightness) returned.
    - max_distance (float): The maximum distance a distance provided can be that won't result in a value of 1 (Max Brightness) returned. 
                            Used to determine the threshold for calculating brightness either as an exponetial or linear function.
    - linear_slope (float): The scalar value used to calculate distance when the linear function is activated.
    - exponential_base (typing.Union[float, int]): The exponential value used when the exponential function is activated."""

    if distance <= min_distance:
        return 0  # Assuming you want very little brightness at close proximity.
    elif distance >= max_distance:
        return 1  # Maximum brightness at the max distance or beyond.
    
    # Define the threshold as halfway through the max distance.
    threshold = max_distance / 2
    
    if distance <= threshold:
        # Linear increase with a customizable slope from min_distance to threshold.
        # Brightness increases linearly based on the distance and slope.
        linear_brightness = (distance - min_distance) / (threshold - min_distance) * linear_slope * 100
        # Ensuring that the linear phase does not exceed the intended maximum at the threshold.
        return round((min(linear_brightness, linear_slope * 100) / 100), 2)
    else:
        # Exponential increase from the end of the linear phase to 100% from threshold to max_distance.
        # Normalize distance to range [0,1] for exponential calculation.
        normalized_dist = (distance - threshold) / (max_distance - threshold)
        # Calculate exponential increase with a base that can be adjusted.
        exponential_brightness = 100 * linear_slope + (100 * (1 - linear_slope) * (normalized_dist ** exponential_base))
        return round((exponential_brightness / 100),2)

def determine_leds_range_for_angle(angle_x: typing.Union[float, int], led_sections: list[tuple[int, int]], hfov_range_list: typing.Union[list[float], list[int]])->typing.Union[tuple, None]:
    """Returns the LEDs to turn on based on the angle of the object provided. This function finds the range this angle lies in based on the list of HFOV ranges, and returns the respective led section from the led_sections list.
    
    Parameters:
    - angle_x (float): The angle of the object detected respective to the camera of the subsystem.
    - led_sections (list[tuple[int, int]]): The list of the seperate sections used to each illuminate an object detected.
    - hfov_range_list (list[float]): The list of hfov regions that correlate to each are of leds to illuminate."""
    i = 0
    while i < len(hfov_range_list)-1:
        if angle_x <= hfov_range_list[i] and angle_x >= hfov_range_list[i+1]:
            return led_sections[i]
        # elif i == 0 and angle_x <= hfov_range_list[i] and angle_x + (hfov_range_list[i]-hfov_range_list[i+1])  >= hfov_range_list[i+1]:
        #     return led_sections[i+1]
        i+=1
    return led_sections[i]


def estimate_distance(found_width: float, focal_length: float, known_width: float):
    """Estimate the distance of an object based on the width found for the object.
    
    Parameters:
    - found_width (float): The width of the object detected in milimeters.
    - focal_length (float): The focal length in pixels of the camera.
    - known_width (float): The known width of the object detected in pixels.
    
    Returns:
    distance (float): The distance of the object measured in meters."""
    distance = (((known_width * focal_length) / found_width) * 2.54 ) / 100
    return distance

def calculate_horz_angle(obj_center_x: float, frame_width: int , hfov: int)->float:
    """Estimates the horizontal angle of the object provided in reference to the center of the camera.
    
    Parameters:
    - obj_center_x (float): UPDATE
    - frame_width (int): The width of the current image in pixels.
    - hfov (int): The horizontal field of view of the camera used to take the image."""

    relative_position = obj_center_x / frame_width - 0.5
    angle = hfov * relative_position
    return angle

def calculate_vert_angle(obj_center_y: float, frame_width: int, vfov: int)->float:
    """Estimates the vertical angle of the object provided in reference to the center of the camera.
    
    Parameters:
    - obj_center_y (float): UPDATE
    - frame_width (int): The width of the current image in pixels.
    - vfov (int): The vertical field of view of the camera used to take the image."""

    relative_position = obj_center_y / frame_width - 0.5
    angle = vfov * relative_position
    return angle

class KeyPointClassifier(object):
    """Acts as a TensorFlow lite Interpreter, used in conjuction with MediaPipe Hands to pefrom gesture recongintion with a trained TensorFlow Lite Model."""

    def __init__(self, model_path: str=r'C:\Users\brand\Documents\seniordesign\OldLITTest\ModelFiles\keypoint_classifier.tflite',num_threads: int=1,):
        """On instantiation, an instance of the TensorFlow Lite Interpreter class is instantiated, tensors are allocated, input details and output details are calculated and stored as attributes.
        
        Parameters:
        - model_path (str): The path to the Tensorflow Lite model.
        - num_threads (int): The number of threads to use when performing inference with the Interpreter. ADVISED NOT TO CHANGE."""

        self.interpreter = Interpreter(model_path=model_path,
                                               num_threads=num_threads)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        return
    
    def perform_hand_gesture_inference(self, landmark_list: list[float],)->int:
        """Performs hand gesture inference with the interpreter attirbute by providing a list of landmark locations as floats. Returns the index of the detected hand gesture label, which directly relates to the 
        label stored at the provided index in the label text file.
        
        Parameters:
        - landmark_list: list[float]: A list of hand landmarks values stored as floats. See MediaPipe https://developers.google.com/mediapipe/solutions/vision/gesture_recognizer#hand_landmark_model_bundle to better understand."""
        
        input_details_tensor_index = self.input_details[0]['index']
        self.interpreter.set_tensor(input_details_tensor_index, np.array([landmark_list], dtype=np.float32))
        self.interpreter.invoke()

        output_details_tensor_index = self.output_details[0]['index']

        result = self.interpreter.get_tensor(output_details_tensor_index)

        result_index = np.argmax(np.squeeze(result))

        return result_index
        
class VideoStream:
    """Camera object that controls video streaming"""
    def __init__(self, camera_index: int, resolution: tuple[int, int] =(640,480), framerate: int = 30, focal_length: float = 1080.1875, hfov: int = 78, vfov: int = 49):
        """Creates an Object for that interfaces with the selected camera and stores data from the live feed in real time.
        Data is stored and the dropped as feed is updated.
        
        Parameters:
        - camera_index (int): The file path to a TensorFlow Lite model.
        - resolution (tuple[int, int]): A flag for creating a model that uses an edgeTPU to perfrom computations.
        - framerate (int): The framerate to display the camera feed at.
        - focal_length (float): The focal length of the camera. 
        - hfov (int): The horizontal field of view of the camera.
        - vfov (int): The vertical field of view of the camera."""

        # Initialize the Camera and the camera image stream
        self.stream = cv2.VideoCapture(camera_index)
        ret = self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ret = self.stream.set(3,resolution[0])
        ret = self.stream.set(4,resolution[1])
        self.video_width = resolution[0]
        self.video_heigth = resolution[1]
        self.focal_length = focal_length
        self.hfov = hfov
        self.vfov = vfov
        # Read first frame from the stream
        (self.grabbed, self.frame) = self.stream.read()
        

	# Variable to control when the camera is stopped
        self.stopped = False

    def start(self):
        """Start the thread that reads frames from the video stream"""
        self.stopped = False
        Thread(target=self.update,args=()).start()
        return self

    def update(self):
        """Keep looping indefinitely until the thread is stopped"""
        while True:
            # If the camera is stopped, stop the thread
            if self.stopped:
                # Close camera resources
                self.stream.release()
                return

            # Otherwise, grab the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        """Return the most recent frame"""
        return self.frame

    def stop(self):
        """Indicate that the camera and thread should be stopped"""
        self.stopped = True


class ObjectDetectionModel:
    """A class used for performing Object Detection/Hand Gesture Recognition. This class can run up to two models simultaneously, where one performs Object Detection for persons, and the other performs hand gesture 
    recognition only in the cropped part of the frame that contains the person detected. This class can make use of an EDGE TPU to perform inference, as well as pass camera feed to a PYSimpleGUI using the LITGUIWithClasses module,
    although other GUI's could be used just as easily through the use of the image_window_name arguement in the constructor. This class also has the ability to be given a callback to send object detection data over a socket connection,
    as illustrated in the example. INSERT GITHUB HERE."""

    input_mean: float = 127.5
    input_std: float = 127.5
    frame_rate_calc: int = 1

    def __init__(self, model_path: str, use_edge_tpu: bool, camera_index: int, label_path: str, 
                 min_conf_threshold: float= 0.6,window: typing.Union[sg.Window, None]=None, image_window_name: typing.Union[str, None]=None, 
                 client_conn: socket.socket = None, thread_lock: threading.Lock = None, ref_person_width: int = 20, hfov: int = 89, vfov:int = 129.46, 
                 resolution: tuple[int, int] =(640,360), focal_length: float = 0,hand_gesture_recognition: bool = False, gesture_tflite_path: typing.Union[str, None] = r'ModelFiles\keypoint_classifier.tflite', 
                 gesture_label_path: typing.Union[str, None] = r'ModelFiles\keypoint_classifier_label.csv') -> None:
        """Creates an Object for performing object detection on a camera feed. Uses either an EdgeTPU or CPU to perform computations.
        
        Parameters:
        - model_path: (str): The file path to a TensorFlow Lite model.
        - use_edge_tpu (bool): A flag for creating a model that uses an edgeTPU to perfrom computations.
        - camera_index (int): The device ID of the camera the user would like to use for this object detection model.
        - label_path (str): The path of the labels used for object detection labeling.
        - min_conf_threshold (float): The confidence interval used to identify object.
        - ref_person_width (int): The width of the reference person for determining distance in inches.
        - hfov (int): The horizontal field of view of the camera used to perform object detection.
        - vfov (int): The vertical field of view of the camera used to perform object detection.
        - resolution (tuple[int, int]): The resolution to operate the camera at and use for performing inference.
        - focal_length (float): The focal length of the camera in pixels.
        - gesture_tflite_path (str): The path to the Gesture Recognition TensorFlow Lite Model.
        - gesture_label_path (str): The path to the Gesture Recognition TensorFlow Lite Model's labels."""

        self.gui_window = window
        self.image_window_name = image_window_name
        self.min_conf_threshold = min_conf_threshold
        self.camera_index = camera_index
        self.client_conn = client_conn
        self.thread_lock = thread_lock
        self.ref_person_width = ref_person_width
        self.freq = cv2.getTickFrequency()
        self.set_interpreter(use_edge_tpu, model_path)
        self.set_labels_from_label_path(label_path)
        self.set_input_details()
        self.set_boxes_clases_and_scores_idxs()
        self.detection_thread = None
        self.detection_active = threading.Event()
        self.current_led_list_of_dicts: list[dict] = []
        self.curr_auto_led_data_list: list[tuple] = []
        self.led_sections: list[tuple[int, int]]
        self.hfov = hfov
        self.vfov = vfov
        self.resolution = resolution
        if focal_length == 0:
            self.focal_length = focal_length_finder(resolution[0], hfov)
        else:
            self.focal_length = focal_length
        self.initalize_hand_recognition_model(gesture_tflite_path, gesture_label_path)
        self.hand_gesture_recognition = hand_gesture_recognition
        return
    
    def initalize_hand_recognition_model(self, gesture_tflite_path: str, gesture_label_path: str):
        """Instantiates a MediaPipe Hands class instance used to detect hand landmarks in an image, as well as an instance of the KeyPointClassifer class used to perform gesture recoginiton on this landmark data using
        a TensorFlow Lite model. Lastly this will store the labels of the models as a list of strings.
        
        Parameters:
        - gesture_tflite_path (str): The path to the Gesture Recognition TensorFlow Lite Model.
        - gesture_label_path (str): The path to the Gesture Recognition TensorFlow Lite Model's labels."""

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.3) #possibly add more arguments for max num hands and min detection confidence.
        self.keypoint_classifier = KeyPointClassifier(gesture_tflite_path)
        with open(gesture_label_path, encoding='utf-8-sig') as f:
            self.keypoint_classifier_labels = csv.reader(f)
            self.keypoint_classifier_labels = [row[0] for row in self.keypoint_classifier_labels]
        return
    
    def set_led_ranges_for_objects(self, number_of_leds: int, number_of_sections: int):
        """Based on the number of LEDs provided, and the number of sections the user would like to split the LEDs into, this function uses a helper to generate a list of tuples that represent LED ranges, and then stores this
        list as an instance attribute.
        
        Parameters:
        - number_of_leds (int): The number of LEDs in a single panel of the LED subsystem, currently on works for 32x8 LED panels.
        - number_of_sections (int): The number of sections to split the LED panel into column-wise."""

        self.led_sections = create_led_tuple_range_list(number_of_leds, number_of_sections)
        self.number_of_sections = number_of_sections
        return
    
    def set_client_conn(self, client_conn: socket.socket):
        """Set the client conn attribute."""
        self.client_conn = client_conn
        return 
    
    def set_thread_lock(self, thread_lock: threading.Lock):
        """Set the thread lock attribute"""
        self.thread_lock = thread_lock
        return
    
    def set_window(self, window: typing.Union[sg.Window, None]):
        """Set the window to pass video stream data to."""
        self.gui_window = window
        return

    def set_image_window(self, image_window: typing.Union[str, None]):
        """Set the name of the image element where data will be passed."""
        self.image_window_name = image_window
        return
    
    def set_send_data_callback(self, callback):
        """Callback is a function"""
        self.send_data_callback = callback
        return

    def start_detection(self):
        """Verifies that the current instance of this class does not already have a thread running that spawned from this method, and then initializes a new instance of the VideoStream class with the camera associated with the current instance of this class.
        To keep control of the threads spawned from this method, we start the main detection loop with the detection thread attribute set during this method. 
        
        This leads to the creation of a new thread performing object detection, and the initialize of an attribute that has control of that thread."""
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_active.set()  # Signal that detection should be active
            self.video_stream = VideoStream(self.camera_index, resolution=self.resolution, hfov=self.hfov, vfov = self.vfov, focal_length=self.focal_length)  # Recreate VideoStream to ensure it's fresh
            self.fov_sections = create_fov_range_list(self.video_stream.hfov, self.number_of_sections)
            self.detection_thread = threading.Thread(target=self.main_detection_loop, daemon=True)
            self.detection_thread.start()
        return
    
    def stop_detection(self):
        """Calls the clear method on the current thread, which kills the current detection thread running from an instance of this class. To turn off the video stream, the stop method is called on the VideoStream instance which terminates the thread use to read frames.
        If there is a server connection active, this will send data to the Server to inform the server that object detection has ended."""

        self.detection_active.clear()  # Signal that detection should stop
        if self.video_stream:
            self.video_stream.stop() 
        time.sleep(3)
        return
    

    def main_detection_loop(self):
        """Performs Object Dectection on the current video stream passed to this instance. This runs while the thread is set, and will terminate the loop and thread running this method once the Thread.Event instance used to control this method is cleared.
        Using helper functions, this method will start the thread reading frammes from the camera used in the current instance, detected all objects in the current frame, draw boxes around them, 
        and send relevant LED data to the subsystem being controled from this instance."""

        self.video_stream.start()
        self.previous_gestures = None
        self.gesture_start_time = None
        while self.detection_active.is_set():
            try:
                self.t1 = cv2.getTickCount()
                self.perform_detection_on_current_frame()
                boxes, classes, scores = self.get_boxes_classes_and_scores_from_current_frame()
                self.loop_over_all_objects_detected(boxes, classes, scores)
            except:
                pass
        self.video_stream.stop()
        return

    def loop_over_all_objects_detected(self, boxes, classes, scores):
        """Iterates over all objects detected in the current frame, draws rectangles around them, places labels, calculates distance, horizontal angle, vertical angle, and uses this data to determine the LEDs to turn on a brightness respective to the distance.
        If there is a connect to a server, this data is sent over the server to a device that can directly interface with the LEDs.
        
        Parameters:
        - boxes: Update
        - classes: Update
        - scores: Update"""

        if self.video_stream.stopped:
            return
        
        curr_auto_led_data_list = []
        hands_in_frame = False
        for i in range(len(scores)):
            if (self.labels[int(classes[i])] == 'person') and ((scores[i] > self.min_conf_threshold) and (scores[i] <= 1.0)):      
                self.get_and_set_current_box_vertices(boxes[i])
                self.draw_rectangle_around_current_box()
                self.set_label_on_obj_in_frame(classes[i], scores[i])
                self.set_mid_point_current_obj()
                self.set_width_of_current_obj()
            else:
                continue
                
            try:
                if self.led_sections:
                    distance = estimate_distance(self.current_obj_width, self.video_stream.focal_length, self.ref_person_width)
                    angle_x = calculate_horz_angle(self.current_obj_mid_point_x, self.video_stream.video_width, self.video_stream.hfov)
                    angle_y = calculate_vert_angle(self.current_obj_mid_point_y, self.video_stream.video_heigth, self.video_stream.hfov)
                    brightness = brightness_based_on_distance(distance)
                    led_tuple = determine_leds_range_for_angle(angle_x=angle_x, led_sections=self.led_sections, hfov_range_list=self.fov_sections)
                    curr_led_data = AutoLEDData(led_tuple, brightness)
                    curr_auto_led_data_list.append(curr_led_data)
                    cv2.putText(self.frame, f'Distance: {round(distance,2)} (Meters)', (self.xmin, self.ymin+30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    cv2.putText(self.frame, f'Angle: {round(angle_x,2)} (Degrees)', (self.xmin, self.ymin+60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            except:
                continue

            try:
                if self.hand_gesture_recognition:
                    cropped_image = self.frame[self.ymin: self.ymax, self.xmin: self.xmax]
                    results = self.find_hands_in_object_detected(cropped_image)
                    if results.multi_hand_landmarks:
                        hands_in_frame = True
                        hand_sign_id = self.draw_hand_landmarks_and_make_gesture_inference(results=results, cropped_image=cropped_image)
                        hand_sign_detected_label = self.keypoint_classifier_labels[hand_sign_id]
                        if self.previous_gestures != hand_sign_detected_label:   
                            self.gesture_start_time = time.time()
                            self.previous_gestures = hand_sign_detected_label
                        elif self.previous_gestures and self.gesture_start_time:
                            duration = time.time() - self.gesture_start_time 
                            if duration > 1:
                                self.handle_hand_gesture_control_event(duration)
            except:
                pass

        if self.hand_gesture_recognition:
            self.check_for_no_hands_or_objects_detected(len(classes), hands_in_frame)        

        try:
            if self.client_conn:
                self.system_led_data.auto_led_data_list = curr_auto_led_data_list  
                self.send_data_callback(False)
        except:
            pass
        
        if self.gui_window:
            try:
                cv2.putText(self.frame,'FPS: {0:.2f}'.format(self.frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)
                image_bytes = cv2.imencode('.png', self.frame)[1].tobytes()
                self.gui_window.write_event_value(f"UPDATE_{self.camera_index}_FRAMES", image_bytes)
            except:
                pass

        t2 = cv2.getTickCount()
        time1 = (t2-self.t1)/self.freq
        self.frame_rate_calc= 1/time1
        if cv2.waitKey(1) == ord('q'):
            self.video_stream.stop()
        return
    
    def check_for_no_hands_or_objects_detected(self, objs_detected: int, hands_in_frame: bool)->None:
        """Used to restart the timer that is tracking how long a gesture is detected for in the camera feed. If no hands or objects are detected in the frame, by default the timer 
        will be reset and the previous hand gesture detected will be set to None to reflect the current frame.
        
        Parameters:
        - objs_detected (int): The number of objects detected in the current frame.
        - hands_in_frame (bool): A flag indicating if any hands were detected in the objects detected in the frame processed."""
        if objs_detected == 0 or not hands_in_frame:
            self.gesture_start_time = None
            self.previous_gestures = None
        return
    
    def draw_hand_landmarks_and_make_gesture_inference(self, results, cropped_image: cv2.Mat)->int:
        """After processing a frame this function is used to perform an inference on the results, where we find the various segments of the hand and draw the landmarks, as well as
        determine the hand gesture found as an integer representing the location on the label found in the list of labels associated with the TFLITE model.
        
        Parameters:
        - results: 
        - cropped_image (cv2.Mat): The current frame that is being used to perform object detection, cropped to only contain the current person detected."""
        for hand_landmarks in results.multi_hand_landmarks:

            mp.solutions.drawing_utils.draw_landmarks(cropped_image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        
            landmark_list = calc_landmark_list(cropped_image, hand_landmarks)

            # Conversion to relative coordinates / normalized coordinates
            pre_processed_landmark_list = pre_process_landmark(
                landmark_list)

            hand_sign_id = self.keypoint_classifier.perform_hand_gesture_inference(pre_processed_landmark_list)
            return hand_sign_id
        
    def find_hands_in_object_detected(self, cropped_image: cv2.Mat):
        """Using MediaPipe, this function determines if there is a hand in the image, and returns the values associated with that hand. If there is no hands, this returns None.
        
        Parameters:
        - cropped_image (cv2.Mat): The current frame that is being used to perform object detection, cropped to only contain the current person detected."""

        cropped_image_rgb = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB)
        results = self.hands.process(cropped_image_rgb)
        return results
    
    def handle_hand_gesture_control_event(self, duration: float):
        """When a hand gesture has been detected for longer than 2 seconds, this function is called and operates as an event handler. Using the label of the current hand gesture and the duration of time the hand gesture has been
        detected, this function will call a helper to interface with the LITGUI.
        
        Parameters:
        - duration: The amount of time the gesture has been detected in seconds."""

        if self.previous_gestures == 'Love':
            self.handle_love_gesture_event(duration)
        elif self.previous_gestures.strip() == 'Thumbs Up':
            self.handle_thumbs_up_gesture_event()
        elif self.previous_gestures.strip() == 'Thumps Down':
            self.handle_thumbs_down_gesture_event()
        elif self.previous_gestures.strip() == 'L':
            self.handle_l_gesture_event()
        elif self.previous_gestures.strip() == 'Pointer':
            self.handle_pointer_gesture_event()
        elif self.previous_gestures.strip() == 'OK':
            self.handle_ok_gesture_event(duration)
        return
    
    def handle_l_gesture_event(self):
        """Sends an event to the GUI window reference passed to this instance. Using the LITGui Event Handler, this event increases the Manual LED Range selected on the GUI by 1 each time it is called."""
        self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTUREINCREASELEDRANGE-", 1)
        return
    
    def handle_pointer_gesture_event(self):
        """Sends an event to the GUI window reference passed to this instance. Using the LITGui Event Handler, this event decreases the Manual LED Range selected on the GUI by 1 each time it is called."""
        self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTUREDECREASELEDRANGE-", 1)
        return
    
    def handle_thumbs_down_gesture_event(self):
        """Sends an event to the GUI window reference passed to this instance. Using the LITGui Event Handler, this event decreases the Manual LED Brightness selected on the GUI by 1 each time it is called."""
        self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTUREDECREASEBRIGHTNESS-", 1)
        return
    
    def handle_thumbs_up_gesture_event(self):
        """Sends an event to the GUI window reference passed to this instance. Using the LITGui Event Handler, this event increases the Manual LED Brightness selected on the GUI by 1 each time it is called."""
        self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTUREINCREASEBRIGHTNESS-", 1)
        return

    def handle_ok_gesture_event(self, duration: float):
        """Sends an event to the GUI window reference passed to this instance. Using the LITGui Event Handler, this event changes the LED Range left to right/ right to left 
         checkbox selected on the GUI by each time it is called."""
        left_to_right_status = ((duration // 2) % 2) == 1 #This function is only called when duration is > 2 so therefore, we are saying the lights will turn off and on every 2 seconds.
        if left_to_right_status:
            self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTURELEDRANGELEFTRIGHT-", True)
        else:
            self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTURELEDRANGERIGHTLEFT-", True)


    def handle_love_gesture_event(self, duration: float):
        """Sends an event to the GUI window reference passed to this instance. Using the LITGui Event Handler, this event changes the All LEDs On checkbox selected on the GUI by each time it is called."""
        all_lights_on_status = ((duration // 2) % 2) == 1 #This function is only called when duration is > 2 so therefore, we are saying the lights will turn off and on every 2 seconds.
        self.gui_window.write_event_value(f"-CAMERA_{self.camera_index}_HANDGESTURETURNONALLLEDS-", all_lights_on_status)
        return
    

    def set_label_on_obj_in_frame(self, class_idx: int, score: float):
        """Places a label on an object detected in the frame with the name of the object, and the confidence score for the object detected."""
        object_name = self.labels[int(class_idx)] # Look up object name from "labels" array using class index
        label = '%s: %d%%' % (object_name, int(score*100)) # Example: 'person: 72%'
        labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
        label_ymin = max(self.ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
        cv2.rectangle(self.frame, (self.xmin, label_ymin-labelSize[1]-10), (self.xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in             
        cv2.putText(self.frame, label, (self.xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text
        return 
    
    def set_width_of_current_obj(self):
        """Calcalutes the width of the current objected detected using the vertices of the box drawn around the object."""

        self.current_obj_width = self.xmax - self.xmin
        return 
    
    def set_mid_point_current_obj(self):
        """Sets the midpoints of the current object in respect to the x and y axis."""

        self.current_obj_mid_point_x = self.xmin + (.5 * (self.xmax - self.xmin))
        self.current_obj_mid_point_y = self.ymin + (.5 * (self.ymax - self.ymin))

    def get_and_set_current_box_vertices(self, boxes):
        """Gets the cordinates of the vertices used to draw boxes around the current image and sets them to class attributes."""

        self.ymin = int(max(1,(boxes[0] * self.video_stream.video_heigth)))
        self.xmin = int(max(1,(boxes[1] * self.video_stream.video_width)))
        self.ymax = int(min(self.video_stream.video_heigth,(boxes[2] * self.video_stream.video_heigth)))
        self.xmax = int(min(self.video_stream.video_width,(boxes[3] * self.video_stream.video_width)))
        return
    
    def draw_rectangle_around_current_box(self):
        """Draws a box around the current object with the vertices calculated."""

        cv2.rectangle(self.frame, (self.xmin,self.ymin), (self.xmax,self.ymax), (10, 255, 0), 2)
        return
    
    def obj_is_person(self, obj):
        """Verify the object detected is a person and not a chair or something."""

        if obj == 'person':
            return True
        return False

    def perform_detection_on_current_frame(self):
        """Using the Tensorflow API, this method performs object detection on the current frame. All boxes, classes, and scores are stored in tensors in the current interpreter instance."""
        
        if self.video_stream.stopped:
            return
        frame1 = self.video_stream.read()
        self.frame = frame1.copy()
        frame_rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (self.width, self.height))
        input_data = np.expand_dims(frame_resized, axis=0)   
        if self.floating_model:
            input_data = (np.float32(input_data) - self.input_mean) / self.input_std
        self.interpreter.set_tensor(self.input_details[0]['index'],input_data)
        self.interpreter.invoke()
    
    def get_boxes_classes_and_scores_from_current_frame(self):
        """Using the get_tensor method from the Interpreter class, we are able to grab the coordinates for the boxes yet to be drawn around each object, the class of each object detected, and the score associated with the detection."""

        if self.video_stream.stopped:
            return
        boxes = self.interpreter.get_tensor(self.output_details[self.boxes_idx]['index'])[0] # Bounding box coordinates of detected objects
        classes = self.interpreter.get_tensor(self.output_details[self.classes_idx]['index'])[0] # Class index of detected objects
        scores = self.interpreter.get_tensor(self.output_details[self.scores_idx]['index'])[0] # Confidence of detected objects
        return boxes, classes, scores
    
    def set_interpreter(self, use_edge_tpu: bool, model_path: str)->None:
        """Sets the interpreter to be used with the settings provided by the user. Can use either a CPU or TPU to perform inference.
        
        Parameters:
        - use_edge_tpu (bool): Enable/Disable the use of an edgeTPU to perform computations.
        - model_path (str): The path to the tflite model used to perform Object Detection."""

        if use_edge_tpu:
            interpreter = self.load_edge_tpu_model(model_path)
        else:
            interpreter = self.load_cpu_model(model_path)
        self.interpreter = interpreter
        self.interpreter.allocate_tensors()
        return
    
    def set_labels_from_label_path(self, label_path: str)->None:
        """Read the labels from the label text file and store them in the labels attibute as a list of strings.
        
        Parameters:
        - label_path (str): The path to the tflite label text file used to label Objects Detected."""

        with open(label_path, 'r') as f:
            self.labels = [line.strip() for line in f.readlines()]  
        if self.labels[0] == '???':
            del(self.labels[0])
        return
    
    def set_boxes_clases_and_scores_idxs(self)->None:
        """Set the indexes for the boxes, classes, and scores index attibutes."""

        if ('StatefulPartitionedCall' in self.outname): # This is a TF2 model
            self.boxes_idx, self.classes_idx, self.scores_idx = 1, 3, 0
        else: # This is a TF1 model
            self.boxes_idx, self.classes_idx, self.scores_idx = 0, 1, 2
        return
    
    def set_input_details(self)->None:
        """UPDATE"""
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.height = self.input_details[0]['shape'][1]
        self.width = self.input_details[0]['shape'][2]
        self.floating_model = (self.input_details[0]['dtype'] == np.float32)
        self.outname = self.output_details[0]['name']


    def load_edge_tpu_model(self, model_path: str)->None:
        """
        Loads a TensorFlow Lite model and creates an interpreter optimized for Edge TPU.

        Parameters:
        - model_path (str): The file path to the TensorFlow Lite model compiled for Edge TPU.

        Returns:
        A TensorFlow Lite Interpreter instance optimized for Edge TPU.
        """
        # Load the TensorFlow Lite model with Edge TPU support.
        interpreter = Interpreter(
            model_path=model_path,
            experimental_delegates=[load_delegate("edgetpu.dll")]
        )        
        return interpreter

    def load_cpu_model(self, model_path: str):
        """
        Loads a TensorFlow Lite model and creates an interpreter using the CPU.
        
        Paramters:
        - model_path: The file path to the Tensorflow Lite model compiled for CPU.
        
        Returns:
        A TensorFlow Lite Interpreter instance optimized for CPU use."""

        tf_interpreter = Interpreter(model_path=model_path)
        return tf_interpreter
    
    @property
    def interpreter(self):
        return self._interpreter

    @interpreter.setter
    def interpreter(self, interpreter)->None:
        # if isinstance(interpreter, Interpreter):
        self._interpreter = interpreter


    @property
    def labels(self):
        return self._labels

    @labels.setter
    def labels(self, labels: list[str])->None:
        if isinstance(labels, list):
            self._labels = labels


    @property
    def input_details(self):
        return self._input_details

    @input_details.setter
    def input_details(self, input_details)->None:
        # if isinstance(input_details):
            self._input_details = input_details
    

    @property
    def output_details(self):
        return self._output_details

    @output_details.setter
    def output_details(self, output_details)->None:
        # if isinstance(input_details):
            self._output_details = output_details


    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, height)->None:
        # if isinstance(input_details):
            self._height = height


    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, width)->None:
        # if isinstance(input_details):
            self._width = width


    @property
    def floating_model(self)->bool:
        return self._floating_model

    @floating_model.setter
    def floating_model(self, floating_model)->None:
        # if isinstance(input_details):
            self._floating_model = floating_model


    @property
    def outname(self):
        return self._outname
    
    @outname.setter
    def outname(self, outname)->None:
        # if isinstance(input_details):
            self._outname = outname



if __name__ == '__main__':
    host = '192.168.1.2'
    port = 5000
    model_path = r'C:\Users\brand\OneDrive\Documents\SeniorDesign\ModelFiles\detect.tflite'
    label_path = r'C:\Users\brand\OneDrive\Documents\SeniorDesign\ModelFiles\labelmap.txt'
    obj_detector_one = ObjectDetectionModel(r'C:\Users\brand\OneDrive\Documents\SeniorDesign\ModelFiles\detect.tflite', False, 0, 
                                        r'C:\Users\brand\OneDrive\Documents\SeniorDesign\ModelFiles\labelmap.txt')
    obj_detector_one.start_detection()