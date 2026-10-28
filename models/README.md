# Face models (OpenCV Zoo)

Used by the lightweight face engine (`FACE_ENGINE=opencv`, the default):

| File | Model | Purpose |
|---|---|---|
| `face_detection_yunet_2023mar.onnx` | YuNet | Finds faces and facial landmarks |
| `face_recognition_sface_2021dec.onnx` | SFace | Turns an aligned face into a 128-number embedding |

Both come from [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo) and are licensed under Apache 2.0.
They're committed here so the app runs offline on hosts that can't download them at start-up.
