
# Direct port of the hificode_OpenCV.c C program minus built-in image
# Last update: March 19, 2016; released under the Creative
# Commons Attribution 4.0 International License (CC BY 4.0), 
# see http://www.seeingwithsound.com/im2sound.htm for details 
#
# Beware that this program runs excruciatingly slowly under Python,
# while the PyPy python JIT compiler does not (yet) support OpenCV

import cv2 as cv
import os, sys, struct, math
import wave
import sys
import pyaudio

#import winsound  # Sound output for Microsoft Windows

FNAME    = 'hificode.wav'       # User-defined parameters
FL       =   500   # Lowest  frequency (Hz) in soundscape
FH       =  5000   # Highest frequency (Hz)              
FS       = 44100   # Sample  frequency (Hz)              
T        =  1.05   # Image to sound conversion time (s)  
D        =     1   # Linear|Exponential=0|1 distribution 
HIFI     =     1   # 8-bit|16-bit=0|1 sound quality      
STEREO   =     1   # Mono|Stereo=0|1 sound selection     
DELAY    =     1   # Nodelay|Delay=0|1 model   (STEREO=1)
FADE     =     1   # Relative fade No|Yes=0|1  (STEREO=1)
DIFFR    =     1   # Diffraction No|Yes=0|1    (STEREO=1)
BSPL     =     1   # Rectangular|B-spline=0|1 time window
BW       =     0   # 16|2-level=0|1 gray format in P[][]  
CAM      =     1   # Use OpenCV camera input No|Yes=0|1  
VIEW     =     1   # Screen view for debugging No|Yes=0|1
CONTRAST =     2   # Contrast enhancement, 0=none

# Coefficients used in rnd()
ir = 0
ia = 9301
ic = 49297
im = 233280

TwoPi = 6.283185307179586476925287
HIST  = (1+HIFI)*(1+STEREO)
WHITE = 1.00
BLACK = 0.00

if CAM:
   N = 176
   M = 64
else:
   N = 64
   M = 64

#if BW:
#else:   

CHUNK = 200000

def playSound(file):
   if sys.platform == "win32":
      winsound.PlaySound(file,winsound.SND_FILENAME)  # Windows only
      #os.system('start %s' %file)                    # Windows only
   elif sys.platform.startswith('linux'): 
      print("No audio player called for Linux")
   else:
      wf = wave.open(file, 'rb')

      p = pyaudio.PyAudio()

      stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True) 

      data = wf.readframes(CHUNK)

      while data != '':
         stream.write(data)
         data = wf.readframes(CHUNK)

      stream.stop_stream()
      stream.close()

      p.terminate()

def wi(fp,i):
   b0 = int(i%256)
   b1 = int((i-b0)/256)
   fp.write(struct.pack('B',b0 & 0xff))
   fp.write(struct.pack('B',b1 & 0xff))

def wl(fp,l):
   i0 = l%65536
   i1 = (l-i0)/65536
   wi(fp,i0)
   wi(fp,i1)

def rnd():
   global ir, ia, ic, im
   ir = (ir*ia+ic) % im
   return ir / (1.0*im)

def main():

   k     = 0
   b     = 0
   d     = D
   ns    = 2 * int(0.5*FS*T)
   m     = int(ns / N)
   sso   = 0 if HIFI else 128
   ssm   = 32768 if HIFI else 128
   scale = 0.5 / math.sqrt(M)
   dt    = 1.0 / FS
   v     = 340.0                                 # v = speed of sound (m/s)
   hs    = 0.20           # hs = characteristic acoustical size of head (m)

   w    = [0 for i in range(M)]
   phi0 = [0 for i in range(M)]
   A    = [[0 for j in range(N)] for i in range(M)]  # M x N pixel matrix

   # Set lin|exp (0|1) frequency distribution and random initial phase 
   if (d): 
      for i in range(0,M): w[i] = TwoPi * FL * pow(1.0* FH/FL,1.0*i/(M-1))
   else: 
      for i in range(0,M): w[i] = TwoPi * FL + TwoPi * (FH-FL)   *i/(M-1)
   for i in range(0,M): phi0[i] = TwoPi * rnd()

   cam_id = 0  # First available OpenCV camera
   # Optionally override ID from command line parameter: python hificode_OpenCV.py cam_id
   if len(sys.argv) > 1: cam_id = int(sys.argv[1])

   try:
      cap = cv.VideoCapture(cam_id)   
      if not cap.isOpened(): 
         raise ValueError('camera ID')
   except ValueError:
      print("Could not open camera", cam_id)
      raise

   # Setting standard capture size, may fail; resize later
   frame = cap.read()  # Dummy read needed with some devices
   cap.set(cv.CAP_PROP_FRAME_WIDTH ,176)
   cap.set(cv.CAP_PROP_FRAME_HEIGHT,144)
      
   if VIEW:  # Screen views only for debugging
      cv.namedWindow('Large', cv.WINDOW_AUTOSIZE);
      cv.namedWindow('Small', cv.WINDOW_AUTOSIZE);
      
   key = 0
   while key != 27:  # Escape key
      ret, frame = cap.read()
   
      if ret == False:
         # Sometimes initial frames fail
         print("Capture failed\n")
         key = cv.waitKey(100)
         continue
         
      tmp = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
      if frame.shape[1] != M or frame.shape[0] != N:
         #cv.resize(tmp, gray, Size(N,M))
         gray = cv.resize(tmp, (N,M), interpolation = cv.INTER_AREA)
      else: gray=tmp
   
      if CAM:  # Set live camera image
         avg = 0.0
         for i in range(M):
            for j in range(N):
               avg += gray[M-1-i,j]
            
         avg = avg / (N * M)
         
         for i in range(M):
            for j in range(N):
               px = gray[M-1-i,j]
               px += CONTRAST*(px - avg)
               if px > 255: px = 255
               if px <   0: px =   0
               gray[M-1-i,j] = px
               if px == 0: A[i][j] = 0
               else: A[i][j] = pow(10.0,(px/16-15)/10.0)  # 2dB steps
   
      if VIEW:  # Screen views only for debugging
         cv.imwrite("hificodeLarge.jpg", frame)
         cv.imshow('Large', frame)
         cv.moveWindow('Large', 20, 20)
         cv.imwrite("hificodeSmall.jpg", gray)
         cv.imshow('Small', gray)
         cv.moveWindow('Small', 220, 20)

      key = cv.waitKey(10)
   
      # Write 8/16-bit mono/stereo .wav file
      fp = open(FNAME,'wb')
      fp.write(bytes('RIFF','UTF-8')); wl(fp,ns*HIST+36); 
      fp.write(bytes('WAVEfmt ','UTF-8')); wl(fp,16); wi(fp,1); 
      wi(fp,2 if STEREO else 1); wl(fp,FS); wl(fp,FS*HIST); wi(fp,HIST); 
      wi(fp,16 if HIFI else 8); fp.write(bytes('data','UTF-8')); wl(fp,ns*HIST)
      tau1 = 0.5 / w[M-1]; tau2 = 0.25 * (tau1*tau1)
      y = yl = yr = z = zl = zr = 0.0
   
      while k < ns and not STEREO:
         if BSPL:
            q = 1.0 * (k%m)/(m-1)
            q2 = 0.5*q*q
         j = int(k / m); j=N-1 if j>N-1 else j; s = 0.0; t = k * dt
         if k < ns/(5*N): s = (2.0*rnd()-1.0) / scale  # "click"
         else: 
            for i in range(0,M):
               if BSPL:  # Quadratic B-spline for smooth C1 time window
                  if j==0: a = (1.0-q2)*A[i][j]+q2*A[i][j+1]
                  elif j==N-1: a = (q2-q+0.5)*A[i][j-1]+(0.5+q-q2)*A[i][j]
                  else: a = (q2-q+0.5)*A[i][j-1]+(0.5+q-q*q)*A[i][j]+q2*A[i][j+1]
               else: a = A[i][j]  # Rectangular time window
               s += a * math.sin(w[i] * t + phi0[i])

         yp = y; y = tau1/dt + tau2/(dt*dt)
         y  = (s + y * yp + tau2/dt * z) / (1.0 + y); z = (y - yp) / dt
         l  = sso + 0.5 + scale * ssm * y  # y = 2nd order filtered s
         if l >= sso-1+ssm: l = sso-1+ssm
         if l < sso-ssm: l = sso-ssm
         ss = int(l) & 0xFFFFFFFF  # Make unsigned int
         if HIFI: wi(fp,ss) 
         else: fp.write(struct.pack('B',ss & 0xff))
         k=k+1
      while k < ns and STEREO:
         if BSPL:
            q = 1.0 * (k%m)/(m-1)
            q2 = 0.5*q*q
         j = int(k / m); j=N-1 if j>N-1 else j        
         r = 1.0 * k/(ns-1);  # Binaural attenuation/delay parameter
         theta = (r-0.5) * TwoPi/3; x = 0.5 * hs * (theta + math.sin(theta))
         tl = tr = k * dt
         if DELAY: tr = tr + x / v  # Time delay model
         x  = abs(x); sl = sr = 0.0; hrtfl = hrtfr = 1.0;
         for i in range(0,M):
            if DIFFR:
               # First order frequency-dependent azimuth diffraction model
               hrtf = 1.0 if (TwoPi*v/w[i] > x) else TwoPi*v/(x*w[i])
               if theta < 0.0: 
                  hrtfl =  1.0; hrtfr = hrtf;
               else:
                  hrtfl = hrtf; hrtfr =  1.0;
            if FADE:
               # Simple frequency-independent relative fade model
               hrtfl *= (1.0-0.7*r)
               hrtfr *= (0.3+0.7*r)
            if BSPL:
               if j==0: a = (1.0-q2)*A[i][j]+q2*A[i][j+1]
               elif j==N-1: a = (q2-q+0.5)*A[i][j-1]+(0.5+q-q2)*A[i][j]
               else: a = (q2-q+0.5)*A[i][j-1]+(0.5+q-q*q)*A[i][j]+q2*A[i][j+1]
            else: a = A[i][j]
            sl = sl + hrtfl * a * math.sin(w[i] * tl + phi0[i])
            sr = sr + hrtfr * a * math.sin(w[i] * tr + phi0[i])
            
         sl = (2.0*rnd()-1.0) / scale if (k < ns/(5*N)) else sl  # Left "click"
         if tl < 0.0: sl = 0.0;
         if tr < 0.0: sr = 0.0;
         ypl = yl; yl = tau1/dt + tau2/(dt*dt)
         yl  = (sl + yl * ypl + tau2/dt * zl) / (1.0 + yl); zl = (yl - ypl) / dt
         ypr = yr; yr = tau1/dt + tau2/(dt*dt)
         yr  = (sr + yr * ypr + tau2/dt * zr) / (1.0 + yr); zr = (yr - ypr) / dt
         l   = sso + 0.5 + scale * ssm * yl
         if l >= sso-1+ssm: l = sso-1+ssm
         if l < sso-ssm: l = sso-ssm
         ss  = int(l) & 0xFFFFFFFF
         # Left channel
         if HIFI: wi(fp,ss) 
         else: fp.write(struct.pack('B',ss & 0xff))
         l   = sso + 0.5 + scale * ssm * yr
         if l >= sso-1+ssm: l = sso-1+ssm 
         if l < sso-ssm: l = sso-ssm
         ss  = int(l) & 0xFFFFFFFF
         # Right channel
         if HIFI: wi(fp,ss) 
         else: fp.write(struct.pack('B',ss & 0xff))
         k=k+1

      fp.close()
      
      playSound("hificode.wav");  # Play the soundscape
      
      k=0  # Reset sample count
   
   cap.release()
   cv.destroyAllWindows()
   return 0

main()
