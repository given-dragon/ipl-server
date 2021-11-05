import pathlib
from PIL import Image
import cv2
import numpy as np
import urllib.request
import time
import math

from img_proc.models import VdoProcModel
from django.core.files.base import File

def image_sending(img_url, human_list=None):
    # print(img_url)    
    model = 'img_proc/face/opencv_face_detector_uint8.pb'
    config = 'img_proc/face/opencv_face_detector.pbtxt'

    human = []
    face_list = []
    net = cv2.dnn.readNet(model, config)

    if net.empty():
        print('Net open failed!')
        exit()

    opener = urllib.request.URLopener()
    url_response = opener.open(img_url)   
    img_array = np.array(bytearray(url_response.read()), dtype=np.uint8) 
    image = cv2.imdecode(img_array, -1)
    # frame = cv2.imread(img)
    # frame = cv2.flip(img_array,1)
    frame = image

    blob = cv2.dnn.blobFromImage(frame, 1, (300, 300), (104, 177, 123))
    net.setInput(blob)
    detect = net.forward()

    detect = detect[0, 0, :, :]
    (h, w) = frame.shape[:2]

    for i in range(detect.shape[0]):
        confidence = detect[i, 2]
        if confidence < 0.5:
            continue

        x1 = int(detect[i, 3] * w)
        y1 = int(detect[i, 4] * h)
        x2 = int(detect[i, 5] * w)
        y2 = int(detect[i, 6] * h)
        human.append([x1,y1,x2,y2])
        # cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0))
        face_img = frame[y1:y2, x1:x2]
        face_list.append(face_img)
        label = ""
        cv2.putText(frame, label, (x1, y1 - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 1, cv2.LINE_AA)

    if human_list is None:
        return face_list

    elif not human_list:
        return frame
    else:
        for i in range(len(human)):
            if i in human_list:   
                rate = int((human[i][2]-human[i][0] + human[i][3]-human[i][1]) /25)
                # -> 탐지된 객체의 크기의 가로 길이와 세로 길이를 합한 값을 사용해서 비율을 구함
                # 25로 나누는게 제일 적당했음..
                face_img = frame[human[i][1]:human[i][3], human[i][0]:human[i][2]]  # 탐지된 얼굴 이미지 crop
                face_img = cv2.resize(face_img, ((human[i][2]-human[i][0])//rate, (human[i][3]-human[i][1])//rate))  # rate 만큼 축소
                face_img = cv2.resize(face_img, (human[i][2]-human[i][0], human[i][3]-human[i][1]), interpolation=cv2.INTER_AREA)  # 확대
                frame[human[i][1]:human[i][3], human[i][0]:human[i][2]] = face_img  # 탐지된 얼굴 영역 모자이크 처리
        return Image.fromarray(frame)

def video_sending(video_url, human_list = None): # 동영상 처리
    model = 'img_proc/face/opencv_face_detector_uint8.pb'
    config = 'img_proc/face/opencv_face_detector.pbtxt'    

    cap = cv2.VideoCapture(video_url)
    if not cap.isOpened():
        print('Camera open failed!')
        exit()

    net = cv2.dnn.readNet(model, config)

    if net.empty():
        print('Net open failed!')
        exit()

    people = []  # 탐지된 객체중 사람의 위치를 저장
    check = [0]*100 # 이미지를 바꿨다면?? 을 확인하는 리스트
    check_real = [0]*100 # 체크리스트만 갖고 체크를 하면 type err가 발생하기 떄문에 여기에 2초 후의 이미지를 저장함
    face_list = [] # 최종적으로 서버로 보낼 얼굴 리스트

    old_time = time.time()  # 시간 측정 시작 (old_time = 기준 시간)


    fourcc = cv2.VideoWriter_fourcc(*'DIVX') # 영상 촬영
    out = cv2.VideoWriter('./img_proc/face/output.avi', fourcc, 30.0, (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))
    # output.avi = 모자이크 처리 된 영상

       
    if human_list is None:

        while True:
            _, frame = cap.read()
            if frame is None:
                break

            blob = cv2.dnn.blobFromImage(frame, 1, (300, 300), (104, 177, 123))
            net.setInput(blob)
            detect = net.forward()

            detect = detect[0, 0, :, :]
            (h, w) = frame.shape[:2]

            for i in range(detect.shape[0]):

                ok = 1  # 새로운 좌표를 집어 넣을까 말까 확인 변수(default: 참)

                confidence = detect[i, 2]
                if confidence < 0.5:
                    break

                x1 = int(detect[i, 3] * w)
                y1 = int(detect[i, 4] * h)
                x2 = int(detect[i, 5] * w)
                y2 = int(detect[i, 6] * h)

                for idx in range(len(people)):  # 왼쪽 위 좌표와 오른쪽 아래 좌표를 확인하기 위해 루프를 반복
                    if math.sqrt((people[idx][0] - x1) ** 2 + (people[idx][1] - y1) ** 2) < 110 or \
                            math.sqrt(
                                (people[idx][2] - x2) ** 2 + (people[idx][3] - y2) ** 2) < 110:  # 만약 리스트 안에 가까운 좌표가 이미 있다면
                        people[idx] = [x1, y1, x2, y2]  # 해당 좌표 값을 갱신

                        if time.time() - old_time > 2.0:  # 기준 시간과 현재 시간이 2초 이상 차이난다면
                            if not check[idx]:  # 2초 후 만약 해당 이미지가 갱신이 된 이미지가 아니라면 -> 최초의 사진으로 부터 2초 후에 갱신이 되지 않았다면
                                check_real[idx] = frame[y1:y2, x1:x2].copy() # 갱신 된 이미지를 check_rea 리스트에 저장 함
                                check[idx] = 1  # check 리스트의 해당 인덱스를 1로 바꿔 갱신이 된 이미지(깔끔한 이미지)임을 알림
                            old_time = time.time()  # 기준 시간을 갱신

                        ok = 0  # ok 값 거짓으로 설정
                        break  # 갱신 후 루프를 종료
                
                if ok == 1:  # 만약 ok가 참이면 새로운 사람이 등장한 것이기 때문에 해당 좌표를 리스트에 집어 넣음
                    people.append([x1, y1, x2, y2]) # 새로운 사람을 리스트에 추가
                    face_list.append(frame[y1:y2, x1:x2].copy()) # 새로운 사람이 추가 됐으므로 새로운 사람의 첫 프레임의 이미지를 face_list에 추가
                
                label = ""
                cv2.putText(frame, label, (x1, y1 - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 1, cv2.LINE_AA)

        for i in range(len(people)):  # face_list에는 첫 프레임의 사람 얼굴만 있으므로 갱신된 얼굴이 있다면 갱신된 얼굴로 변경
            if check_real != 0:       # 만약 check_real 값이 0이 아니라면 -> 갱신이 되었다면
                face_list[i] = check_real[i]    # 해당 이미지를 갱신된 이미지로 변경 함
        

        return face_list
    else:

        while True:
            _, frame = cap.read()
            if frame is None:
                break

            blob = cv2.dnn.blobFromImage(frame, 1, (300, 300), (104, 177, 123))
            net.setInput(blob)
            detect = net.forward()

            detect = detect[0, 0, :, :]
            (h, w) = frame.shape[:2]

            for i in range(detect.shape[0]):

                ok = 1  # 새로운 좌표를 집어 넣을까 말까 확인 변수(default: 참)

                confidence = detect[i, 2]
                if confidence < 0.5:
                    break

                x1 = int(detect[i, 3] * w)
                y1 = int(detect[i, 4] * h)
                x2 = int(detect[i, 5] * w)
                y2 = int(detect[i, 6] * h)

                for idx in range(len(people)):  # 왼쪽 위 좌표와 오른쪽 아래 좌표를 확인하기 위해 루프를 반복
                    if math.sqrt((people[idx][0] - x1) ** 2 + (people[idx][1] - y1) ** 2) < 110 or \
                            math.sqrt(
                                (people[idx][2] - x2) ** 2 + (people[idx][3] - y2) ** 2) < 110:  # 만약 리스트 안에 가까운 좌표가 이미 있다면
                        people[idx] = [x1, y1, x2, y2]  # 해당 좌표 값을 갱신

                        if time.time() - old_time > 2.0:  # 기준 시간과 현재 시간이 2초 이상 차이난다면
                            if not check[idx]:  # 2초 후 만약 해당 이미지가 갱신이 된 이미지가 아니라면 -> 최초의 사진으로 부터 2초 후에 갱신이 되지 않았다면
                                check_real[idx] = frame[y1:y2, x1:x2].copy() # 갱신 된 이미지를 check_rea 리스트에 저장 함
                                check[idx] = 1  # check 리스트의 해당 인덱스를 1로 바꿔 갱신이 된 이미지(깔끔한 이미지)임을 알림
                            old_time = time.time()  # 기준 시간을 갱신

                        ok = 0  # ok 값 거짓으로 설정
                        break  # 갱신 후 루프를 종료
                
                if ok == 1:  # 만약 ok가 참이면 새로운 사람이 등장한 것이기 때문에 해당 좌표를 리스트에 집어 넣음
                    people.append([x1, y1, x2, y2]) # 새로운 사람을 리스트에 추가
                    face_list.append(frame[y1:y2, x1:x2].copy()) # 새로운 사람이 추가 됐으므로 새로운 사람의 첫 프레임의 이미지를 face_list에 추가
                

                for human in range(len(people)):
                    if human in human_list:
                        rate = int((x2-x1+y2-y1) / 25)
                        face_img = frame[y1:y2, x1:x2]  # 탐지된 얼굴 이미지 crop
                        face_img = cv2.resize(face_img, ((x2-x1)//rate, (y2-y1)//rate))  # 축소
                        face_img = cv2.resize(face_img, (x2-x1, y2-y1), interpolation=cv2.INTER_AREA)  # 확대
                        frame[y1:y2, x1:x2] = face_img  # 탐지된 얼굴 영역 모자이크 처리

                label = ""
                cv2.putText(frame, label, (x1, y1 - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 1, cv2.LINE_AA)

            # cv2.imshow('frame', frame)
            out.write(frame)

        for i in range(len(people)):  # face_list에는 첫 프레임의 사람 얼굴만 있으므로 갱신된 얼굴이 있다면 갱신된 얼굴로 변경
            if check_real != 0:       # 만약 check_real 값이 0이 아니라면 -> 갱신이 되었다면
                face_list[i] = check_real[i]    # 해당 이미지를 갱신된 이미지로 변경 함

        out.release()

        vdo_str = pathlib.Path(video_url)
        vdo_name = vdo_str.name.split('.')[0]
        video = File(open('./img_proc/face/output.avi','rb'), vdo_name+'.avi')
        video_obj = VdoProcModel.objects.create(video = video)
        print('https://bucket-for-ipl.s3.amazonaws.com/'+str(video_obj.video))
        return 'https://bucket-for-ipl.s3.amazonaws.com/'+str(video_obj.video)

    
    
    
    
    
    

