// Browser-side webcam helpers shared by the scan, live-session and enroll pages.
// The camera runs on the visitor's device; only single JPEG frames are sent to the server.

const AttendCamera = {
  stream: null,

  async start(videoEl) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('This browser does not support camera access (HTTPS is required).');
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    videoEl.srcObject = this.stream;
    await videoEl.play();
  },

  stop(videoEl) {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (videoEl) videoEl.srcObject = null;
  },

  isRunning() {
    return this.stream !== null;
  },

  // Grab the current video frame as a JPEG data URL.
  capture(videoEl, quality = 0.85) {
    if (!videoEl.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = videoEl.videoWidth;
    canvas.height = videoEl.videoHeight;
    canvas.getContext('2d').drawImage(videoEl, 0, 0);
    return canvas.toDataURL('image/jpeg', quality);
  },

  describeError(err) {
    if (err && err.name === 'NotAllowedError') return 'Camera permission was blocked. Allow camera access in your browser and try again.';
    if (err && err.name === 'NotFoundError') return 'No camera was found on this device.';
    return (err && err.message) || 'Could not start the camera.';
  },
};
