import cv2

# 0 通常代表預設的內建攝影機；若有外接鏡頭，可改嘗試 1 或 2
cap = cv2.VideoCapture(0)

# 檢查攝影機是否成功開啟
if not cap.isOpened():
    print("錯誤：無法開啟攝影機。請檢查權限或鏡頭連線。")
    exit()

# 設定畫面的寬高（可選）
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

while True:
    # 讀取一幀畫面 (ret: 是否成功讀取, frame: 影像矩陣)
    ret, frame = cap.read()

    if not ret:
        print("無法取得影像畫面，結束執行。")
        break

    # 在原生視窗中顯示畫面
    cv2.imshow('Native Camera Feed', frame)

    # 按下鍵盤 'q' 鍵即可退出迴圈 (1ms 延遲)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 釋放攝影機資源並關閉原生視窗
cap.release()
cv2.destroyAllWindows()