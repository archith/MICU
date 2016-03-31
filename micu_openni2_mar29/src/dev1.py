#!/usr/bin/python
'''
Created on Jan 31, 2014

Version 2 -- Large revision change
    Jun 20 2015 - OpenNI2.2
    Sep 17, 2015 - added laxed and strict server synchronization 
                         cvs with framenuber, local timestamp, server timestap
                         added try to connect to server if active. 
                         Code wont crash if server or other clients fail.
Dependencies:
1) openni2.2 acquire: depth, rgb, & mask(user pixels) from primesense device
2) primesense 2.2.0.30 python binaries for openni2
3) numpy to convert openni structures/data to mat arrays
4) opencv for displaying, saving frames/images, and generating videos
5) pytables (hdf5) for bookkeeping

Current features:
    1) Saves png for types for the run: rgb, depth, mask, skel, all
        rgbdm is saved at 4:1. See "frames" folder
            save_frames_flag=True
    
    2) Save frames/screenshots rgb and dmap (raw depth, not depth for display)
        * s-key to "screen" capture to screens folder
        * f-key to save nf-frames to frames folder
    
    3) Displays the images: normal, medium, or small
        rgb and depth

    4) Create an HDF5 file (pytable)
        name: 'ICU_dev<#>.h5'
        group: 'action'
        table: 'actor'
            ||globalframe|viewframe|timestamp|viewangle|actionlabel|actorlabel|
             |locatime_stimestamp|.. etc|
    
    5) tcp client
        devid: dev1, dev2, ..devN
        Add/Remove access by removing/adding devs from server_threads.py
        
            client  commands: connect, check, close
            servers response: save, wait

Execution:
    WIRED NET
        #Open a terminal, set server IP, and run the server
        ctrl+alt+t
        sudo ifconfig eth0 192.168.0.11 netmask 255.255.255.0
        # Activate server
        python server_threads.py

@author: Carlos Torres <carlitos408@gmail.com>
'''
from primesense import openni2
from primesense import _openni2 as c_api

import cv2, cv, sys, time, os, csv

import numpy as np

from time import localtime, strftime, gmtime

import client



## Drawing
radius = 10
green  = (0,255,0)
blue   = (255,0,0)
red    = (0,0,255)
colors = [green, blue, red]
#confs  = [1.0, 0.5, 0.0]

x = 480/2
y = 640/2


## Array to store the image modalities+overlayed_skeleton (4images)
#rgb   = np.zeros((480,640,3), np.uint8)
#rgbdm = np.zeros((480,640*4, 3), np.uint8)


## Path of the OpenNI redistribution OpenNI2.so or OpenNI2.dll
# Windows
#dist = 'C:\Program Files\OpenNI2\Redist\OpenNI2.dll'
# OMAP
#dist = '/home/carlos/Install/kinect/OpenNI2-Linux-ARM-2.2/Redist/'
# Linux

##omap
dist = '/home/carlos/Install/kinect/OpenNI2-Linux-Arm-2.2/Redist/'
##alienware
#dist='/home/carlos/libs/kinect2/OpenNI2/Redist'

## initialize openni and check
openni2.initialize(dist)
if (openni2.is_initialized()):
    print "openNI2 initialized"
else:
    print "openNI2 not initialized"
#if

## Register the device
dev = openni2.Device.open_any()

## create the streams stream
rgb_stream = dev.create_color_stream()
depth_stream = dev.create_depth_stream()


w = 640
h = 480


##configure the depth_stream
depth_stream.set_video_mode(c_api.OniVideoMode(pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_DEPTH_1_MM, resolutionX=w, resolutionY=h, fps=30))
## Check and configure the depth_stream -- set automatically based on bus speed
#print 'The rgb video mode is', rgb_stream.get_video_mode() # Checks rgb video configuration
rgb_stream.set_video_mode(c_api.OniVideoMode(pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_RGB888, resolutionX=w, resolutionY=h, fps=30))


## 

## Configure the mirroring, which by default is enabled (True)
depth_stream.set_mirroring_enabled(False)
rgb_stream.set_mirroring_enabled(False)

## start the stream
rgb_stream.start()
depth_stream.start()

## synchronize the streams
dev.set_depth_color_sync_enabled(True) # synchronize the streams

## IMPORTANT: ALIGN DEPTH2RGB (depth wrapped to match rgb stream)
dev.set_image_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)


def get_rgb():
    """
    Returns numpy 3L ndarray to represent the rgb image.
    """
    bgr   = np.fromstring(rgb_stream.read_frame().get_buffer_as_uint8(),dtype=np.uint8).reshape(480,640,3)
    rgb   = cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
    return rgb    
#get_rgb


def get_depth():
    """
    Returns numpy ndarrays representing the raw and ranged depth images.
    Outputs:
        dmap:= distancemap in mm, 1L ndarray, dtype=uint16, min=0, max=2**12-1
        d4d := depth for dislay, 3L ndarray, dtype=uint8, min=0, max=255    
    Note1: 
        fromstring is faster than asarray or frombuffer
    Note2:     
        .reshape(120,160) #smaller image for faster response 
                OMAP/ARM default video configuration
        .reshape(240,320) # Used to MATCH RGB Image (OMAP/ARM)
                Requires .set_video_mode
    """
    dmap = np.fromstring(depth_stream.read_frame().get_buffer_as_uint16(),dtype=np.uint16).reshape(480,640)  # Works & It's FAST
    d4d  = np.uint8(dmap.astype(float) *255/ 2**12-1) # Correct the range. Depth images are 12bits
    d4d  = cv2.cvtColor(d4d,cv2.COLOR_GRAY2RGB)
    return dmap, d4d
#get_depth


def createFolders(actor='patient_0'):
    """
    Checks if a sdcard is connected and if a folder exists under 
        root/icudata/patient_<number>
    If it exists a new name is created
        newname = root/icudata/patient_<number+1>
        foldername = newfoldername
    Ultimately, creates folders for frames and csv files and returns paths.
        folder4frames='root/icudata/patient_<number+1>/frames/'
        folder4csv   ='root/icudata/patient_<number+1>/csv/'
    """
    
    ## Two storage locations: media or local
    if len(os.listdir('/media/')) >0:
        #sdcard = os.listdir('/media/')[0]
        #if len(os.listdir('/media/'+usr))>0: #check to see if there are any cards
        sdcard = os.listdir('/media/')[0]
        media = '/media/'+sdcard+'/'
        root = media+'icudata1/'
        storage = 'External'
    else: #if not, then save on local hdd
        usr = os.listdir('/home/')[0]
        local = '/home/'+usr+'/Documents/Python/openni2_omap/ICU_omap_v2/'
        root = local+'icudata1/'
        storage='Local'
    #end ifsdcards
    
    ## check existence of directory.
    folder = root+actor
    name,idx = actor.split('_')    
    done = False
    while not done:
        if os.path.isdir(folder):
            'Directory exists {}... renaming!'.format(folder)
            name,idx = actor.split('_')
            idx = str(int(idx)+1)
            print idx
            actor = ('_').join([name,idx])
            folder = root+actor
            
        else:
            print 'Directory {} Doesnt Exist. Creating It'.format(folder)
            folder4frames = folder+'/frames/'
            #folder4vids = folder+'/videos/'
            folder4csv    = folder+'/csv/'
            os.makedirs(folder4frames+'/rgb/')
            os.makedirs(folder4frames+'/depth/')
            os.makedirs(folder4csv)
            done = True
    #print '{} storage location {}'.format(storage, root)
    #print 'Directory for frames: {}'.format(folder4frames)
    #print 'Directory for csv file: {}'.format(folder4csv)
    return folder4frames,folder4csv
# createFolders()


def save_frames(frame, rgb, depth, p="../data/frames/"):
    """
    Saves the images to as lossless pngs and appends the frame number n
    """
    # save te images to the path
    print "Saving image {} to {}".format(frame, p)
    cv2.imwrite(p+'/rgb/'+"rgb_"  + str(frame)+".png",rgb)
    cv2.imwrite(p+'/depth/'+"depth_"+ str(frame)+".png",depth)
    return
# save_frames


def talk2server(cmd='connect', dev=1):
    """
    Communicate with server 'if active'
    inputs:
        cmd = str 'connect' ,'check' , 'sync' or 'close'
        dev = int 1, 2, ... n, (must be declared in server_threads.py)
    outputs:
        server_reponse = str, server response
        server_time = str, server timestamp
    usage:
    server_response, server_time = talk2server(cmd='connect',dev=1)
        
    """
    try:
        server_response, server_time = client.check_tcp_server(cmd=cmd,dev=dev).split("_")
    except: # noserver response
        server_time="na"
        server_response="none"
    # print "server reponse: {} and timestamp: {}".format(server_response, server_time)
    return server_response, server_time
    


## ======== MAIN =========
if __name__ == '__main__':
    
    time.sleep(20) # secs pause! for startup
    
    dev = 1
    synctype = 'relaxed'
    actorname = "patient_0"
    test_flag = True
    test_frames = 5000000

    
    ## Runtime and Controls
    nf  = 10 #172800# 60*60*24*2 # Number of video frames in one day at 2 fps
    f   = 1  # frame counter
    tic = 0
    run_time   = 0
    total_t    = 0
    done = False
    
    ## TCP communication
    #client.check_tcp_server(cmd='connect',dev=dev)
    server_response, server_time = talk2server(cmd='connect',dev=dev)    
    
    ## Flags
    vis_frames      = True# True   # display frames
    save_frames_flag= False  # save all frames
    generate_videos = False  # use the saved frames to generate .avi files

    #timelabel = strftime("%a, %d %b %Y %H:%M:%S:%s +0000", gmtime())
    #print 'time:', timelabel

    ## The folders for all data
    folder4frames,folder4csv=createFolders(actorname)
	
	## The videowriter
    fourcc=cv2.cv.CV_FOURCC('X','V','I','D')
	video = cv2.VideoWriter(p_dst+vidname+".avi",fourcc, fps=10, frameSize=(h,w))

    

    # bufsize = 2**27; #64Mbytes in bits
    ## open/create csv file
    with open(folder4csv+'data'+str(dev)+'.csv','w') as fp:#, bufsize) as fp:
        # Set the writer with comma delimiter
        writer=csv.writer(fp, delimiter=',')
        
        # Get the first timestamp
        tic = time.time()
        start_t = tic
        
        # Write zero data point
        datarow=['start time', tic, ' ', strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())]
        writer.writerow(datarow)
        
        # Write column names:
        colnames =['frame','localtic=gmtime','servertic=gmtime']
        writer.writerow((colnames))

        
    
        ##--- main loop ---
        done     = False
        while not done: # view <= nviews
            #server_time="na"
            #server_response="none"
        
            ## RGB-D Streams
            rgb   = get_rgb()
            dmap, d4d = get_depth()

            ## Display the streams
            #cv2.imshow("RGB-D Stream", rgbd)
            #cv2.waitKey(1)
            # run_time += time.time()-tic
            # Check the flags
            if vis_frames: # Display the streams
                rgbdm = np.hstack((rgb,d4d))
                #rgbdm_small = rgbdm # orginal size
                #rgbdm_small = cv2.resize(rgbdm,(1280,240)) # medium
                rgbdm_small = cv2.resize(rgbdm,(640,240)) # smallest        
                cv2.imshow("1:4 scale", rgbdm_small) # small
                ## === Keyboard Commands ===
                key = cv2.waitKey(1) & 255
                if key == 27: 
                    print "Terminating code!"
                    done = True                
            #check vis_frames
            
            #Poll the server:
            #server_response, server_time = client.check_tcp_server(cmd='check',dev=dev).split("_")
            server_response, server_time = talk2server(cmd='sync',dev=dev)
            localtime = time.time()
            run_time += localtime-tic
            
            ## === check synchronization type
            if synctype =='strict':
                if server_response == 'save':
                    #print 'Saving -- server response!'
                    save_frames(f,rgb,dmap,p=folder4frames)
                    # Write Datarows
                    datarow =[f,run_time, strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()),server_time]
                    writer.writerow(datarow)
                    f+=1
            elif synctype == 'relaxed':
                save_frames(f,rgb,dmap,p=folder4frames)
                # Write Datarows
                datarow = [f,run_time,server_time]
                writer.writerow(datarow)
                f+=1
            else:
                print "synchronization type unknown"
                
                
            if test_flag and (f==test_frames): 
                print "Terminating code!"
                done = True
            #elif chr(key) =='s':  #s-key to save current screen
            #    save_frames(f,rgb,dmap,p=folder4screens)
            
            #if
            # --- keyboard commands ---
        # while
        #Write the last rows
        fps = f/(run_time)
        datarow=[['fps', fps],['runtime',run_time]]
        writer.writerows(datarow)
        # end csv file        
   
    # TERMINATE
    print "===Terminating code!==="
    # Close carmine context and stop device    
    print "\tClosing carmine context"    
    rgb_stream.stop()
    depth_stream.stop()
    openni2.unload()

    # Disconnect the client from the server
    print "\tDisconecting client"
    #client.check_tcp_server(cmd='close',dev=dev)
    server_response, server_time = talk2server(cmd='close',dev=dev)    
    

    # Release video/image resources
    cv2.destroyAllWindows()
    #vidout.release()
            
    # print some timing information:
    print "Time metrics:" 
    print ("\ttotal run time is %.2f secs" %run_time)
    print ("\tfps: %.2f" %fps)

    # generate the .avi video files
    if (save_frames and generate_videos):
        print "Video generated~"
        os.system ("python carmine_generate_vids.py ")

    sys.exit(0)
#if __main__


#run ("test","victor_side_1")
run("t0", "a0")
