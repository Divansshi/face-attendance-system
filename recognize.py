import sys
import json

def run(img1_path, img2_path):
    try:
        from deepface import DeepFace
        result = DeepFace.verify(
            img1_path=img1_path,
            img2_path=img2_path,
            enforce_detection=False,
            silent=True
        )
        print(json.dumps({'verified': result['verified']}))
    except Exception as e:
        print(json.dumps({'verified': False, 'error': str(e)}))

if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])