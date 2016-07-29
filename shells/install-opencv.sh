#!/bin/sh
# KEEP UBUNTU MATE
# Ref:
# http://www.pyimagesearch.com/2015/10/26/how-to-install-opencv-3-on-raspbian-jessie/

sudo apt-get -y update
sudo apt-get -y upgrade
sudo apt-get -y dist-upgrade
sudo apt-get -y autoremove
sudo rpi-update


# INSTALL THE DEPENDENCIES

# Build tools:
sudo apt-get install -y build-essential cmake pkg-config
# image I/O packages to load image file formats: JPEG, PNG, TIFF, etc.:

sudo apt-get install libjpeg-dev libtiff5-dev libjasper-dev libpng12-dev

# video I/O packages. These packages allow us to load various video file formats as well as work with video streams
sudo apt-get install libavcodec-dev libavformat-dev libswscale-dev libv4l-dev

sudo apt-get install libxvidcore-dev libx264-dev

# We need to install the GTK development library so we can compile the highgui  sub-module of OpenCV, which allows us to display images to our screen and build simple GUI interfaces:
sudo apt-get install libgtk2.0-dev

# matrix operations) can be optimized using added dependencies
sudo apt-get install libatlas-base-dev gfortran

# python headers and bindings
sudo apt-get install python2.7-dev python3-dev


# INSTALL THE LIBRARY (YOU CAN CHANGE '3.1.0' FOR THE LAST STABLE VERSION)

sudo apt-get install -y unzip wget

wget https://github.com/Itseez/opencv/archive/3.1.0.zip
unzip 3.1.0.zip
rm 3.1.0.zip

#OpenCV 3 (which includes features such as SIFT and SURF), be sure to grab the opencv_contrib repo as well. (Note: Make sure your opencv  and opencv_contrib  versions match up, otherwise you will run into errors during compilation. For example, if I download v3.0.0 of opencv , then I’ll want to download v3.0.0 of opencv_contrib  as well):
wget -O opencv_contrib.zip https://github.com/Itseez/opencv_contrib/archive/3.1.0.zip
unzip opencv_contrib.zip

#mv opencv-3.1.0 OpenCV
#cd OpenCV
#mkdir build
#cd build
#cmake -DWITH_QT=ON -DWITH_OPENGL=ON -DFORCE_VTK=ON -DWITH_TBB=ON -DWITH_GDAL=ON -DWITH_XINE=ON -DBUILD_EXAMPLES=ON ..
#make -j4
#sudo make install
#sudo ldconfig

## Step #3: Setup Python
# Python for our OpenCV compile is to install pip
wget https://bootstrap.pypa.io/get-pip.py
sudo python get-pip.py





# EXECUTE SOME OPENCV EXAMPLES AND COMPILE A DEMONSTRATION

# To complete this step, please visit 'http://milq.github.io/install-opencv-ubuntu-debian'.
