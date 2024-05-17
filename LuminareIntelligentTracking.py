import LITGuiWithClasses
import LITSubsystemInterface
import ObjectDetectionModel
import multiprocessing
import argparse
from ObjectDetectionModel import ObjectDetectionModel
from LITSubsystemInterface import LITSubsystemData
from LITGuiWithClasses import LITGUI
import warnings
warnings.filterwarnings("ignore")

def run_gui_process(camera_idx: int, number_of_leds: int = 256, numbmer_of_sections: int = 8, host:str = '', port: str = '', 
                    object_detect_status: bool=False, model_path: str='', label_path: str='',use_tpu: bool = False, background_images_dir: str = r'BackgroundImages', hand_gesture_recogin: bool = True):
    model_path = r'C:\Users\brand\Documents\seniordesign\OldLITTest\ModelFiles\detect.tflite'
    label_path = r'C:\Users\brand\Documents\seniordesign\OldLITTest\ModelFiles\labelmap.txt'
    if object_detect_status:
        from tensorflow.lite.python.interpreter import Interpreter 
        from tensorflow.lite.python.interpreter import load_delegate
        object_detection_model = ObjectDetectionModel(model_path=model_path, use_edge_tpu=use_tpu, camera_index=camera_idx, label_path=label_path,resolution=(720, 405), hand_gesture_recognition=hand_gesture_recogin)
        lit_subsystem_data = LITSubsystemData(camera_idx, object_detection_model, number_of_leds=number_of_leds, number_of_sections=numbmer_of_sections, host=host, port=port)
        gui = LITGUI(lit_subsystem_data, background_images_dir=background_images_dir)
    else:
        lit_subsystem_data = LITSubsystemData(camera_idx, number_of_leds=256, number_of_sections=8, host=host, port=port)
        gui = LITGUI(lit_subsystem_data, background_images_dir=background_images_dir)
    gui.start_event_loop()
    return

def start_gui(camera_idx: int, number_of_leds: int = 256, numbmer_of_sections: int = 8, host:str = '', port: str = '', 
              object_detect_status: bool = False, model_path: str='', label_path: str='', use_tpu: bool = False, background_images_dir: str = r'BackgroundImages', hand_gesture_recogin: bool = False)->multiprocessing.Process:
    p = multiprocessing.Process(target=run_gui_process, args=(camera_idx,number_of_leds, numbmer_of_sections, host, port, object_detect_status, model_path, label_path, use_tpu, background_images_dir, hand_gesture_recogin))
    p.start()
    return p

def set_command_line_arguments()->argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--performance_mode", help="(Optional) Run subsystems in parallel", action="store_true")
    parser.add_argument("--host", help='(Optional) Local IP address of the server for sending data', action='store')
    # parser.add_argument("--ports", help='(Optional) Local IP address of the server for sending data', action='store')
    # parser.add_argument("--host", help='(Optional) Local IP address of the server for sending data', action='store')

    return parser


if __name__ == '__main__':
    parser = set_command_line_arguments()
    args = parser.parse_args()
    performance_status = args.performance_mode
    object_detection_tflite_path = r'ModelFiles\detect.tflite'
    object_detection_edgetpu_path = r'ModelFiles\edgetpu.tflite'
    object_detection_label_path = r'ModelFiles\labelmap.txt'
    wifi_host='192.168.0.220'
    ethernet_host = '192.168.1.2'
    ports = [5000, 5001]
    if performance_status:
        process1 = start_gui(camera_idx=0, number_of_leds=256, numbmer_of_sections=8, host=ethernet_host, port=ports[1], object_detect_status=True, model_path=object_detection_tflite_path,
                              label_path=object_detection_label_path, use_tpu=False, background_images_dir = r'BackgroundImages')
        process2 = start_gui(camera_idx=1, number_of_leds=256, numbmer_of_sections=8, host=ethernet_host, port=ports[0], object_detect_status=True, model_path=object_detection_tflite_path,
                              label_path=object_detection_label_path, use_tpu=False, background_images_dir = r'BackgroundImages')
        process1.join()
        process2.join()
    else:
        object_detection_model_one = ObjectDetectionModel(model_path=object_detection_tflite_path, use_edge_tpu=False, camera_index=0, label_path=object_detection_label_path, resolution=(720, 405))
        object_detection_model_two = ObjectDetectionModel(model_path=object_detection_tflite_path, use_edge_tpu=False, camera_index=1, label_path=object_detection_label_path, resolution=(720, 405))
        subsystem_one = LITSubsystemData(0,object_detection_model_one, number_of_leds=256, number_of_sections=8, host=ethernet_host, port= ports[1])
        subsystem_two = LITSubsystemData(1,object_detection_model_two, number_of_leds=256, number_of_sections=8, host=ethernet_host, port= ports[0])

        subsystem_list = [subsystem_one, subsystem_two]
        lit_gui = LITGUI(subsystem_list, background_images_dir=r'BackgroundImages')
        lit_gui.start_event_loop()
