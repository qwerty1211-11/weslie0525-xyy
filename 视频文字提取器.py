import cv2
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
VIDEO_PATH = "C:\lenovo\山海·南界.mp4"
SAMPLE_INTERVAL = 30
def extract_text_from_video(video_path, interval):
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    result_text = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % interval == 0:
            text = pytesseract.image_to_string(frame, lang='chi_sim+eng')
            text = text.strip()
            if text:
                result_text.append(text)
        frame_count += 1
    cap.release()
    unique_texts = list(set(result_text))
    return "\n".join(unique_texts)
if __name__ == "__main__":
    content = extract_text_from_video(VIDEO_PATH, SAMPLE_INTERVAL)
    print("提取到的视频文字：\n", content)
    # 写入txt保存
    with open("视频提取文字.txt", "w", encoding="utf-8") as f:
        f.write(content)