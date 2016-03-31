'''
Created on Jan 31, 2014
Versions:
    Feb1
    Feb2
    May9
    May30
    Jul23 - corrected depth map generation (no longer using histogram/frame)
    Aug 11 - Optmized rgb and depth capture/update functions
    Aug 17 - Added NTP
Uses:
1) pyopenni to acquire: depth, rgb, & mask(user pixels) from primesense device
2) numpy to convert openni structures/data to mat arrays
3) opencv for display and video recording
4) pytables (hdf5) for data rcording


Status: operational
    It can record/displays frames (w or w/o user deteced) and store the info
    display device frames; vis=True
    save current view by pressing spacebar (stored in "../data/screen/" folder
    saves frames in "../data/frames/" folder; requires save_frames_flag=True
    generates avi videos "../data/videos/"; requires generate_videos=True
    terminate code by pressing "Esc"


Current features:
    1) Saves png for types for the run: rgb, depth, mask, skel, all
        rgbdm is saved at 4:1. See "frames" folder
            save_frames_flag=True
    2) Current view/frame can be saved by pressing spacebar. See "screen" folder
        NOTE: skelton & 'useful' mask appear when user is being tracked, else
            blank frames are saved.

    2) Displays the images: normal, medium, or small
        rgb, skeleton_joints, depth,mask
        Currently displaying small

    3) Extracts joints (beow is original pyopenni format)
        type(joint) -> class
        type(joint.point) -> list
        len(joint.point) -> 3
        type(joint.confidence)-> float

    4) Realworld and Projective joint coordinates stored in dictionaries
        pyopenni joints -> r_jnts={} and p_jnts={}
        keys:= str, ["head", "torso", "l_shoulder", ... r_shoulder, etc.]
        values: = list,[x,y,z,confidence]where elements are floats

    5) Create an HDF5 file (pytable)
        name: 'mmARC_device#.h5'
        group: 'action'
        table: 'actor'
            ||globalframe|viewframe|jnt_confidence|realworld[xyz]|...
             |projective[xyz]|timestamp|viewangle|actionlabel|actorlabel|...
             |locatime_stimestamp||


ToDo:
    1) Needs a time/scheduler to begin recording in a synchronized manner
    2) Create a dictionary w frame number, user id, and joint+confidence
    3) Try NTP for timestamp synchronization


DONE
    1) DONE: Save joints to respective frame
    2) DONE: Save ALL info to hdf5 <--> Requires arctable.py "ARCtable"
        action: str, name of the action E.g., kick
        angle: int, orientation angle wrt to front facing dev. E.g., [0:40:320]
        actor: str, actor name
        dev: str, device indx label # -> "dev1"
        projective: dictionary, projective 15-joint coordinates.
            key := joint; value:= [x,y,z,conf], list of floats
        realworld: dictionary, real world 15-joint coordinates [x y z]
        time: foat, time stamp from system/computer
        frame number : frame
        name: str, name used to save the rgb image (use: str.replace(rgb,mask))
        status: Bool, currently tracking a user (any user) o the scene

Useful - but not required (TODO):
    1) Dictionary: carmine={}
        keys=[tracking, confidence, projective, realWorld, timestamp, device,
              action, actor, angle, imname,userid]#, pose, sequence, bmom, bRT,
              gRT, gmom, hogRGB, hogDepth]

@author: Carlos Torres <carlitos408@gmail.com>
'''
#!/usr/bin/python

from openni import *
import numpy as np
import cv
import sys
import cv2
import time
import os
import tables as tb
import arctable as arc
from tables import *
from time import localtime, strftime

import ntplib # NTP
from time import ctime


#c_ntp = ntplib.NTPClient()
#response = c_ntp.request('pool.ntp.org')




XML_FILE = 'config.xml'
#MAX_DEPTH_SIZE = 10000

context = Context()
context.init_from_xml_file(XML_FILE)

depth_generator = DepthGenerator()
depth_generator.create(context)

image_generator = ImageGenerator()
image_generator.create(context)

user_generator = UserGenerator()
user_generator.create(context)

user_generator.alternative_view_point_cap.set_view_point(image_generator)

#palette = [(0, 0, 0), (255, 0, 0), (255, 0, 0), (255, 0, 0)]

#grayscale_palette = tuple([(i, i, i) for i in range(256)])


#histogram   = None
depth_map   = None

# drawing skeleton of detected user(s)
radius = 10
green  = (0,255,0)
blue   = (255,0,0)
red    = (0,0,255)
colors = [green, blue, red]
confs  = [1.0, 0.5, 0.0]

x = 480/2
y = 640/2

# skeleton-joint handler:
handler  = {"head":         SKEL_HEAD,
            "neck":         SKEL_NECK,
            "torso":        SKEL_TORSO,
            "l_shoulder":   SKEL_LEFT_SHOULDER,
            "l_elbow":      SKEL_LEFT_ELBOW,
            "l_hand":       SKEL_LEFT_HAND,
            "l_hip":        SKEL_LEFT_HIP,
            "l_knee":       SKEL_LEFT_KNEE,
            "l_foot":       SKEL_LEFT_FOOT,
            "r_shoulder":   SKEL_RIGHT_SHOULDER,
            "r_elbow":      SKEL_RIGHT_ELBOW,
            "r_hand":       SKEL_RIGHT_HAND,
            "r_hip":        SKEL_RIGHT_HIP,
            "r_knee":       SKEL_RIGHT_KNEE,
            "r_foot":       SKEL_RIGHT_FOOT
          }
# handler


# array to store the image modalities+overlayed_skeleton (4images)
rgb   = np.zeros((480,640,3), np.uint8)
rgbdm = np.zeros((480,640*4, 3), np.uint8)

#check and/or generate the folder to store the images:
p = "../data/frames/"
if not os.path.isdir(p):
    print "creating folder"
    os.makedirs(p)
#if
screen = "../data/screenshots/"
if not os.path.isdir(screen):
    print "creating folder"
    os.makedirs(screen)
#if

# Pose to use to calibrate the user
pose_to_use ='Psi'

# Obtain the skeleton & pose detection capabilities
skel_cap = user_generator.skeleton_cap
pose_cap = user_generator.pose_detection_cap

def createFolder(folder="../data/"):
    """Checks if a folder exists and create folder(s) complete path if it
    does not exist.
    E.g.,
    createFolder("../data/<actionname>/<actorname>/frames/") # -> video frames
    createFolder("../data/<actionname>/<actorname>/screenshoots/") # -> screencaptures"""
    if not os.path.isdir(folder):
        print "Creating folder and its path."
        os.makedirs(folder)
# createFolder()


# ====== Declare the callbacks
def new_user(src, id):
    print "1/4 User {} detected. Looking for pose..." .format(id)
    pose_cap.start_detection(pose_to_use, id)
#new_user()

def pose_detected(src, pose, id):
    print "2/4 Detected pose {} on user {}. Requesting calibration..." .format(pose,id)
    pose_cap.stop_detection(id)
    skel_cap.request_calibration(id, True)
#pose_detected

def calibration_start(src, id):
    print "3/4 Calibration started for user {}." .format(id)

def calibration_complete(src, id, status):
    if status == CALIBRATION_STATUS_OK:
        print "4/4 User {} calibrated successfully! Starting to track." .format(id)
        skel_cap.start_tracking(id)
    else:
        print "ERR User {} failed to calibrate. Restarting process." .format(id)
        new_user(user_generator, id)

def lost_user(src, id):
    print "--- User {} lost." .format(id)

# Register them
user_generator.register_user_cb(new_user, lost_user)
pose_cap.register_pose_detected_cb(pose_detected)
skel_cap.register_c_start_cb(calibration_start)
skel_cap.register_c_complete_cb(calibration_complete)

# Set the profile
skel_cap.set_profile(SKEL_PROFILE_ALL)

# Start generating
context.start_generating_all()
print "0/4 Starting to detect users. Press Esc to exit."


def timeEvent(t=2,d=2):
    c = localtime() # struct
    print 'First executed at time: %d:%d:%.2f\n' %(c.tm_hour, c.tm_min, c.tm_sec)
    ctrl = False
    done = False
    v = np.asarray(xrange(0,60,t)) # 1D array of  ticks
    while not done:
        c = localtime()
        m,s = c.tm_min, c.tm_sec/60.0 #min & seconds(converted to minutes
        dst = np.abs(v-(m+s+d))
        idx = np.argmin(dst)
        if (not ctrl):
            tick = v[idx]
            mm = tick-m-s
            print 'Time left: %d mins & %d secs. Looking for tick %d\n'%(np.floor(mm),(mm-np.floor(mm))*60 , tick)
            ctrl = True
        if m == tick:
            c = localtime()
            print 'Reached tick %dhr:%dmm:%dss\n'%(c.tm_hour, c.tm_min, c.tm_sec)
            r = 1
            k = m
            ctrl = False
            done = True
    print 'Event Timed!'
    return r,k
#timeEvent()


def capture_depth():
    """ Create np.array from Carmine raw depthmap string using 16 or 8 bits
    depth = np.fromstring(depth_generator.get_raw_depth_map_8(), "uint8").reshape(480, 640)
    max = 255 #=(2**8)-1"""
    depth = np.fromstring(depth_generator.get_raw_depth_map(), "uint16").reshape(480, 640)
    max = 4095 # = (2**12)-1
    depth_norm=(depth.astype(float) * 255/max).astype(np.uint8)
    d4d = cv2.cvtColor(depth_norm, cv2.COLOR_GRAY2RGB) # depth4Display
    return depth, d4d
#capture_depth


def capture_rgb():
    '''Get rgb stream from primesense and convert it to an rgb numpy array'''
    rgb = np.fromstring(image_generator.get_raw_image_map_bgr(), dtype=np.uint8).reshape(480, 640, 3)
    return rgb
# capture_rgb


def capture_mask():
    '''Get mask from pyopenni user_generator [0,1].
    mask:= numpy array, single channel in [0 255] range'''
    #mask:= binary [0,1], converted to [0,255]
    mask = np.uint8(np.asarray(user_generator.get_user_pixels(0)).reshape(480, 640)*255)
    return mask
#capture_mask

def save_frames(globalframe, rgb,depth,mask,skel, rgbdm, p='../data/frames/'):#,depth,mask, n):
    '''Saves the images to as lossless pngs and appends the frame number n'''
    # save te images to the path
    cv2.imwrite(p+"rgb_"+str(globalframe)+".png",rgb)
    cv2.imwrite(p+"depth_"+str(globalframe)+".png",depth)
    cv2.imwrite(p+"mask_"+str(globalframe)+".png",mask)
    cv2.imwrite(p+"skel_"+str(globalframe)+".png",skel)
    #cv2.imwrite(p+"all_"+str(globalframe)+".png",rgbdm)
    return
# save_frames

def convert2projective(joint):
    """Convert pyopenni joint_object into a list of floats:[x,y, z, confidence]
    x, y, z, and confidence are floats"""
##    print 'jnt: ', [joint.point]
    pt = depth_generator.to_projective([joint.point])[0]
    projective_joint= [float(pt[0]), float(pt[1]), float(pt[2])]#, joint.confidence]
    return projective_joint
#convert2projective

def get_joints(id):
    """Extract/convert real-world joints to projective
    key:= , str joint label [head, neck, lshoulder, rshoulder]
    value:= float, [x,y,z, confidence]
    input:
        id:= int, user id number for which joint coorindates are needed
    outputs:
        p_joints:= dictionary, projective joints coordinates
        r_joints:= dictionary of real-world joint coordinates (same format)
            value:= list [float, float, float ,float]
            key:= str, joint label (see below)
    >>> get_joints(int)-> dictionary, dictionary
    Accessing dictionary:
        >>> p[head] ->  [20.0, 30.0, 10.0, 0.5] """
    # initialize the dictionaries:
    r={}
    p={}
    real_w = {}
    for key in handler.keys():
        r[key] = skel_cap.get_joint_position(id,handler[key])# -> [str,str,str,float]
        # Convert to projective
        p[key] = convert2projective(r[key])
        # Convert the data in the original dictonary to format
        real_w[key] = [ float(r[key].point[0]),float(r[key].point[1]),
                        float(r[key].point[2]),r[key].confidence]
        # confidences:
    return p, real_w
# get_joints


def get_joint_arrays(id):
    """Extract/convert real-world joints to projective
    key:= , str joint label [head, neck, lshoulder, rshoulder]
    value:= float, [x,y,z, confidence]
    input:
        id:= int, user id number for which joint coorindates are needed
    outputs:
    old:
        p_joints:= dictionary, projective joints coordinates
        r_joints:= dictionary of real-world joint coordinates (same format)
            value:= list [float, float, float ,float]
            key:= str, joint label (see below)
        >>> get_joints(int)-> dictionary, dictionary
        Accessing dictionary:
            >>> p[head] ->  [20.0, 30.0, 10.0, 0.5]
    NEW:
        confidences = np.array; shape=(15,1)
        proj_coords = np.array; shape=(15,3)
        real_coords = np.array; shape=(15,3)
    >>> get_joints(int)-> array(15,3),array(15,3),array(15,1)
    >>> print handler.keys() #for order or joints or see 'handler '
    """
    # initialize the dictionaries:
    r={}
    p={}
    real_w    = {}
    real_list = []
    proj_list = []
    conf_list =[]
    for key in handler.keys():
        r[key] = skel_cap.get_joint_position(id,handler[key])# -> [str,str,str,float]
        # Convert to projective
        p[key] = convert2projective(r[key])
        # Convert the data in the original dictonary to format
        real_w[key] = [ float(r[key].point[0]),float(r[key].point[1]),
                        float(r[key].point[2])]#,r[key].confidence]
        #convert to list
        conf_list.append(r[key].confidence)
        proj_list.append(p[key])
        real_list.append(real_w[key])
    # convert to array
    confidences = (np.array(conf_list)).reshape(15,1)
    proj_coords = (np.array(proj_list)).reshape(15,3)
    real_coords = (np.array(real_list)).reshape(15,3)
    return proj_coords, real_coords, confidences
# get_joint_arrays




## ===========================================================================
# Functions for the hdf5 file management
## ---------------------------------------------------------------------------
# check if h5 file exists
def checkh5exists(filename):
    '''Check if hdf5 file exists
    if not: create it and open is to add new groups and tables
    if yes: open it to append new data --> new group and/or table
    input:
        filename: str'''
    if not os.path.isfile(filename):
        print "creating hdf5 file: ", filename
        h5file= openFile(filename, mode="w", title = "TESTmmARC_device1")
        group = h5file.createGroup("/", actionname,"actions")
    else:
        print "open hdf5 to append: ", filename
        h5file= openFile(filename, mode="a", title = "TESTmmARC_device1")
        group = "/"+actionname

    return h5file, group
#checkh5exists

def terminatecode():
    ''' It terminates the running script and performs the following:
    1) Close the hdf5file'''
    context.stop_generating_all()
    h5file.close()
#terminatecode


## ======== MAIN =========
if __name__== "__main__":
    # Take in the arguments (action, actor) from the user
    if len(sys.argv) <3:
        print "Usage: python main.py <actionname> <actorname>"# <state>"
        sys.exit()
    # if len

    ## === hdf5 file: recoding parameters
    minutes     = 10 # record-time in minutes
    dev         = 2  # device number
    viewframe   = 0
    globalframe = 0
    run_time    = 0

    nviews      = 1           # number of views from which data is collected
    arcstep     = 40          # angular step size
    view        = 0
    # ---

    # flags
    vis             = True   # display frames
    save_frames_flag= True  # save all frames
    generate_videos = False  # use the saved frames to generate .avi files

##    timelabel = strftime("%a, %d %b %Y %H:%M:%S:%s +0000", gmtime())
##    print 'time:', timelabel

    actionname   = sys.argv[1] # actionname = "testing"
    actorname    = sys.argv[2] # actorname  =  "carlos2"
#    statename    = sys.argv[3] # statename  = "s1"
    statename = "test"

    # The folders for the frames:
    folder4frames = "../data/"+actionname+"/"+actorname+"/"+statename+"/frames/"
    folder4screen = "../data/"+actionname+"/"+actorname+"/"+statename+"/screenshoots/"


    createFolder(folder4frames) # -> video frames
    createFolder(folder4screen) # -> screencaptures
    # hdf5 file
    h5filename   = "../data/"+actionname+"/"+actorname+"/"+statename+"/mmSLEEP_"+str(dev)+".h5"


    # Verify that the hdf5 file exists
    h5file, group  = checkh5exists(h5filename)

    #create a new table: devTable
    devTable = h5file.createTable(group, actorname, arc.ARCtable, actorname)

    # initialize the arrays for the joint coordinates & confidences
    confidences = np.zeros((15,1), dtype=float)
    p_jnts = np.zeros((15,3), dtype=float)
    r_jnts = np.zeros((15,3), dtype=float)

    ##--- main loop ---
    rr,kk = timeEvent(1,.5)
    done     = False
    while not done: # view <= nviews
        if view == nviews:
            print "Terminating code!"
            print "closing hdf5 file"
            done = True

        # checking the running time
        if run_time >= minutes*60:
            view +=1
            print "Moving onto the next view: ", view*arcstep
            print "\t Pausing for 5 seconds to record again"
            viewframe = 0
            time.sleep(5) # sleep 5 seconds
            print "Begin recording... again!"
            run_time = 0

        # if time

        # Check user keyboard inputs
        key = cv2.waitKey(1)
        if (key == 27):
            print "Terminating code!"
            print "closing hdf5 file"
            done = True
        elif key ==ord(' '): #spacebar to save a frame
            print 'Saving image indexed: ', globalframe
            save_frames(globalframe,rgb,depth, mask, skel, rgbdm_small, screen, p=folder4screen)
        #if

        # populate the table one row at a time: devRow
        devRow = devTable.row
        context.wait_any_update_all()
        tic = time.time()
        # collect images from carmine - even w/o a user detected
        rgb   = capture_rgb()
        #depth,d4d = update_depth_image()
        depth, d4d = capture_depth()

        skel  = np.ones((480,640, 3), np.uint8)*255
        cv2.putText(skel,"NO USER",(x,y), cv2.FONT_HERSHEY_PLAIN, 2.0, red,
        thickness=2, lineType=cv2.CV_AA)
        mask  = capture_mask()

        # Extract head position of each tracked user
        for id in user_generator.users: # Consider only one user by ussing [0]
            if skel_cap.is_tracking(id):
                # Get the frames
                rgb   = capture_rgb()
                depth,d4d = capture_depth()
                mask  = capture_mask()
                skel  = rgb.copy()
                p_jnts, r_jnts, confidences = get_joint_arrays(id) # projective and real coordnates
                #draw joints:
                for i in np.arange(14):
                    center = (int(p_jnts[i,0]), int(p_jnts[i,1]))
                    conf = confidences[i]
                    color = colors[confs.index(conf)]
                    cv2.circle(skel, center ,radius, color, thickness=-2)
            #if skel_cap
        #for id

        devRow['globalframe'] = globalframe
        devRow['viewframe']   = viewframe
        devRow['confidence']  = confidences
        devRow['realworld']   = r_jnts
        devRow['projective']  = p_jnts
        devRow['timestamp']   = time.time()
        devRow['viewangle']   = view*arcstep
        devRow['actionlabel'] = 0
        devRow['actorlabel']  = 1
        devRow['actionname']  = statename #actionname
        devRow['actorname']   = actorname
        devRow['timestring']  = strftime("%a, %d %b %Y %H:%M:%S:%s +0000", localtime())
        #devRow['timestring']  = strftime("%a, %d %b %Y %H:%M:%S:%s +0000", gmtime())
        #devRow['timestring']  = ctime(response.tx_time)

        devRow.append()

        # check the flags
        if (vis or save_frames_flag):
            rgbdm = np.hstack((rgb,skel,d4d,cv2.cvtColor(mask,cv2.COLOR_GRAY2RGB)))
            #rgbdm_small = rgbdm # orginal size
            rgbdm_small = cv2.resize(rgbdm,(1280,240)) # medium
            #rgbdm_small = cv2.resize(rgbdm,(640,120)) # smallest
            if vis:
                # display the concatenated images
                cv2.imshow("4:1 scale", rgbdm_small) # small
            if save_frames_flag:
                # Save the frames as png's
                save_frames(globalframe,rgb,depth, mask, skel, rgbdm_small, p=folder4frames)
        #if vis or save_frames
        viewframe   += 1
        globalframe += 1
        toc = time.time()
        run_time += toc-tic
        #print ("continuous fps: %.2f" % globalframe/run_time)
    # while

    fps = globalframe/run_time

    # print some timing information:
    print ("total run time is %.2f secs" %run_time)
    print ("fps: %.2f" %fps)

    # Close the hdf5 file
    h5file.close()

    # close carmine context and stop device
    context.stop_generating_all()

    # generate the .avi video files
    if (save_frames and generate_videos):
        os.system ("python carmine_generate_vids.py ")

    sys.exit(0)
#if __main__
