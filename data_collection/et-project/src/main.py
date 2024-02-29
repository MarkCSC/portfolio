"""
This script allows you to crop and store multiple snippets from images stored in a directory
Useful for turning scanned image into text and latex using Mathpix tool

Usage:
    main.py [--image_dir IMAGE_DIR] [--snip_dir SNIP_DIR]

Options:
    -h --help               Show this help message and exit.
    --image_dir IMAGE_DIR   Directory for importing original image.
                            Default is 'image' in the current working directory.
    --snip_dir SNIP_DIR     Directory for exporting cropped snippet.
                            Default is 'snip' in the current working directory.
"""


import argparse
import os
import logging
import time

import cv2
import queue
import datetime
import threading
from config import load_config

from mathpix_connect import Mathpix

# setting the logging format
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename=os.path.join(os.path.dirname(os.getcwd()),
                                          "log",
                                          time.strftime("log_%Y-%m-%d_%H-%M-%S.log")))


def check_progress():
    """
    Check for previous progress of cropping images using progress.txt
    """
    # check for previous progress
    # if found, read it and return a list
    # if not found, create a progress file, and return a empty ls
    try:
        with open("../progress.txt", 'r') as p:
            prev_read = [fn.strip() for fn in p.readlines()]
            logging.info(f"Successfully read previous progress, {len(prev_read)} files read before") 

        return prev_read
    
    except FileNotFoundError:
        logging.warning("progress.txt not found")
        return []
    
    except Exception as e:
        logging.error(e)
        print("FATAL: Unexpected error occured for checking previous progress, check log file for information")
        exit(1)
    

def queue_init(prev_read_ls):
    """
    for initializing the photo queue for cropping
    prev_read_ls: list that stores the file that to be **excluted** during the reading progress
    """

    file_queue = queue.Queue()

    f_count = 0
    non_f_count = 0
    f_read_before = 0
    for f in os.listdir(args.image_dir):
        f_path = os.path.join(args.image_dir, f)
        if os.path.isfile(f_path):
            if f_path not in prev_read_ls:
                file_queue.put(f_path)
                f_count += 1
            else:
                f_read_before += 1
        else:
            logging.warning(f"Not a file: {f_path}")
            non_f_count += 1
    
    logging.info(f"{f_count} file stored to queue")
    logging.info(f"{f_read_before} file in image_dir read previously, not stored to queue")
    logging.info(f"{non_f_count} cannot be stored to queue, not a file")

    return file_queue


def main():

    # inner callback function for listen mouse action
    def click_and_crop(event, x, y, flags, params):
        nonlocal x1, y1, x2, y2, is_dragging
        if event == cv2.EVENT_LBUTTONDOWN and not is_dragging:
            x1, y1 = x, y
            is_dragging = True
        
        elif event == cv2.EVENT_MOUSEMOVE:
            if is_dragging == True:
                x2, y2 = x, y
                image_copy = img.copy()
                cv2.rectangle(image_copy, (x1, y1), (x, y), (0, 255, 0), 2)
                cv2.imshow('Image', image_copy)
            
        elif event == cv2.EVENT_LBUTTONUP:
            if is_dragging == True:
                x2, y2 = x, y
                is_dragging = False
                image_copy = img.copy()
                cv2.rectangle(image_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.imshow('Image', image_copy)
    
    # ===================================
    # 0. load config
    # ===================================
    config = load_config()
                
    # ===================================
    # 1. read all filename from IMAGE_DIR
    # ===================================
    prev_read_ls = check_progress()
    
    # =============================================
    # 2. read and store files in the dir to a queue
    # =============================================
    file_queue = queue_init(prev_read_ls)


    # =============================================
    # 3. Initialize mathpix opject for operation
    # =============================================
    mp = Mathpix()

    # =====================================================
    # 4. read all image in opencv one by one and process it
    # =====================================================
    
    # created progress.txt if not exist, or open it for appending image_path
    
    logging.info("opened stream for progress.txt")
    
    close_window = False

    mp_thread_ls = [] # for join() the threads at the end of the program
    db_thread_ls = []

    while not file_queue.empty() and not close_window:
        # get the head image of the queue
        current_img_path = file_queue.get()
        logging.info(f"Process Image: {current_img_path}")

        # open it 
        img = cv2.imread(current_img_path)

        # # or resize and open it (not that good in my opinion maybe my monitor is too small)
        # if img.shape[0] > config["screen_size"]["width"]:
        #     print(img.shape)
        #     aspect_ratio = img.shape[1] / img.shape[0] #height/width
        #     new_height = int(config["screen_size"]["height"])
        #     new_width = int(new_height * aspect_ratio)
        #     img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_NEAREST)

        img_clone = img.copy()

        saved_rectangle_ls = []

        # loop for drawing boxes on another image copy
        while True:
            cv2.imshow('Image', img)

            x1, y1, x2, y2 = -1, -1, -1, -1 # reset coordiante, coordinate x1y1 for down and x2y2 for release

            is_dragging = False
            cv2.setMouseCallback('Image', click_and_crop) # mouse callback operation

            key = cv2.waitKey(0)

            # Enter: save all the selected region to snips and process next photo (if exisit)
            # s: confirm and save the last rectangle 
            if key == 13: # Enter key

                # not write to process tracking file if -i argument
                if not args.ignore:
                    with open("../progress.txt", 'a') as f:
                        f.write(f"{current_img_path}\n")
                    logging.info(f"Saved {current_img_path} to progress.txt")

                # generate file names, save cropped image
                for i, coord in enumerate(saved_rectangle_ls):
                    now = datetime.datetime.now()
                    cropped_path = os.path.join(args.snip_dir, now.strftime("%Y-%m-%d_%H-%M-%S")+ "_" + str(i) +".jpg")
                    
                    ### modify here 
                    w_success = cv2.imwrite(cropped_path, 
                                img_clone[coord[0][1]:coord[1][1], coord[0][0]:coord[1][0]])
                    
                    if w_success and args.mathpix:
                        fetch_thread = threading.Thread(target=mp.checkOne, args=(cropped_path,))
                        mp_thread_ls.append(fetch_thread)
                        fetch_thread.start()
                    
                    if w_success and args.mongodb:
                        save_db_thread = threading.Thread(target=mp.storeMongo, args=(cropped_path,))
                        db_thread_ls.append(save_db_thread)
                        save_db_thread.start()

                    logging.info(f"Snippet saved: {cropped_path}")

                logging.info(f"finished processing image: {current_img_path}")
                break

            elif key == ord('s'): # 's' key to confirm the last rectangle on image
                is_dragging = False

                # prevent duplicating the rectangle and save the region on image
                rec_coordinate = ((min(x1,x2), min(y1,y2)), (max(x1,x2), max(y1,y2)))
                if rec_coordinate not in saved_rectangle_ls and (x1, y1) != (x2, y2) and x2 != -1 and y2 != -1:
                    saved_rectangle_ls.append(rec_coordinate)
                    img = cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.imshow('Image', img)
            
            # Check if the window is closed by user
            if cv2.getWindowProperty("Image", cv2.WND_PROP_VISIBLE) < 1:
                close_window = True
                break
        
        cv2.destroyAllWindows()
    
    # close all mathpix api thread
    for trd in mp_thread_ls:
        trd.join()

    # close all store to db thread
    for trd in db_thread_ls:
        trd.join()

    logging.info("end of images queue loop or user close window")

    logging.info("Exit")



if __name__ == "__main__":

    logging.info("Starting")
    
    # parse arguments
    parser = argparse.ArgumentParser("Images to snippets")
    parser.add_argument("--image_dir", 
                        default=os.path.join(os.path.dirname(os.getcwd()), 'image'), 
                        help="directory for importing original image")
    parser.add_argument("--snip_dir",
                        default=os.path.join(os.path.dirname(os.getcwd()), 'snip'),
                        help="directory for exporting cropped snippet")
    parser.add_argument("-i", 
                        "--ignore", 
                        action="store_true", 
                        help="original photos will not save record to process.txt")
    parser.add_argument("-m",
                        "--mathpix",
                        action="store_true",
                        help="directory for exporting cropped snippet")
    
    parser.add_argument("-db",
                        "--mongodb",
                        action="store_true",
                        help="store mathpix return to mongodb")
    
    args = parser.parse_args()

    # check args dir exist and log it
    if not os.path.isdir(args.image_dir):
        logging.error(f"image_dir doesn't exist: {args.image_dir}")
        logging.error(f"terminate")
        print("FATAL: terminated, please check error log")
        exit(1)
    logging.info(f"image_dir: {args.image_dir}")    

    if not os.path.isdir(args.snip_dir):
        logging.error(f"snip_dir doesn't exist: {args.snip_dir}")
        logging.error(f"terminate")
        print("FATAL: terminated, please check error log")
        exit(1)
    logging.info(f"snip_dir: {args.snip_dir}")

    main()