from cv2 import IMWRITE_JPEG2000_COMPRESSION_X1000
from flask import Flask, render_template, Response, request
from flask_sqlalchemy import SQLAlchemy
import inference_script
import cv2
import os
import sys
from datetime import datetime
import time
from threading import Thread

global capture, rec_frame, switch, rec, out, run_model
capture = 0
switch = 1
rec = 0


# making directory to save pictures
try:
    os.mkdir('./saved')

except OSError as error:
    pass


app = Flask(__name__, template_folder='./templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
camera = cv2.VideoCapture(0)
db = SQLAlchemy(app)
save_path = '\saved'


def record(out):
    global rec_frame
    while(rec):
        time.sleep(0.05)
        out.write(rec_frame)


def gen_frames():  # generate frame by frame from camera
    global out, capture, rec_frame

    while camera.isOpened():
        success, frame = camera.read()
        # print(success)
        if success:
            if(capture):
                # print(capture)
                capture = 0
                now = datetime.now()

                now = now.strftime("%d/%m/%Y %H:%M:%S")
                now.replace(':', '_')

                path_f = '\saved\shot.jpg'
                print(path_f)
                cv2.imwrite(path_f, frame)

            if(rec):
                rec_frame = frame
                frame = cv2.putText(cv2.flip(
                    frame, 1), "Recording...", (0, 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 4)
                frame = cv2.flip(frame, 1)

            try:
                ret, buffer = cv2.imencode('.jpg', cv2.flip(frame, 1))
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception as e:
                camera.release()
                cv2.destroyAllWindows()

        else:
            pass


class auxiliary_sens(db.Model):
    __tablename__ = 'auxiliary-sens'
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, default=datetime.now())
    smoke_reading = db.Column(db.Integer, nullable=False)
    moisture_reading = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return 'auxiliary-sens ID is %r taken at %r' % (self.id, self.datetime)


class inference_readings(db.Model):
    __tablename__ = 'inference-readings'
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, default=datetime.now())
    fuzzy_reading = db.Column(db.Integer, nullable=False)
    model_reading = db.Column(db.Integer, nullable=False)
    net_reading = db.Column(db.Integer, nullable=False)
    sum_reading = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return 'inference-readings ID is %r taken at %r and accumulation sum is %r' % (self.id, self.datetime, self.sum)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video-stream')
def video_stream():
    return render_template('video-stream.html')


@app.route('/video-stream/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/stream_requests', methods=['POST', 'GET'])
def sr_tasks():
    global switch, camera
    if request.method == 'POST':
        if request.form.get('capture') == 'Capture':
            global capture
            capture = 1

        elif request.form.get('stop') == 'Play / Pause':

            if(switch == 1):
                switch = 0
                camera.release()
                cv2.destroyAllWindows()

            else:
                camera = cv2.VideoCapture(0)
                switch = 1
        elif request.form.get('rec') == 'Start / Stop Recording':
            global rec, out
            rec = not rec
            if(rec):
                now = datetime.now()
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter('vid_{}.avi'.format(
                    str(now).replace(":", '')), fourcc, 20.0, (640, 480))
                # Start new thread for recording the video
                thread = Thread(target=record, args=[out, ])
                thread.start()
            elif(rec == False):
                out.release()

    elif request.method == 'GET':
        return render_template('video-stream.html')
    return render_template('video-stream.html')


@app.route('/inference_requests', methods=['POST', 'GET'])
def ir_tasks():
    if request.method == 'POST':
        if request.form.get('run_model') == 'Run Model':

            while(1):
                
                if (request.form.get('stop_model') == 'Stop Model'):
                    break

                # yahoooooooooooooooooooooo
                arr = inference_script.main()
                data_in = inference_readings(
                    fuzzy_reading=arr[0], model_reading=arr[1], net_reading=arr[2], sum_reading=arr[3])
                db.session.add(data_in)
                db.session.commit()
                my_data = inference_readings.query.order_by(inference_readings.datetime)
                return render_template('live-inference.html', my_data = my_data)
                #alter this
                time.sleep(4)

    elif request.method == 'GET':
        my_data = inference_readings.query.order_by(inference_readings.datetime)
        return render_template('live-inference.html', my_data = my_data)
        
    my_data = inference_readings.query.order_by(inference_readings.datetime)
    return render_template('live-inference.html', my_data = my_data)

@app.route('/auxiliary-requests', methods = ['POST', 'GET'])
def ar_tasks():
    if request.method == 'POST':
        data_out_aux = request.data
        #convert bytes to string
        data_out_str = str(data_out_aux, 'UTF-8')
        data_out_str_list = data_out_str.split()
        data_out_str_list[0] = int(float(data_out_str_list[0]))
        data_out_str_list[1] = int(float(data_out_str_list[1]))
        
        data_in_aux = auxiliary_sens(moisture_reading=  data_out_str_list[0], smoke_reading=  data_out_str_list[1])
        db.session.add(data_in_aux)
        db.session.commit()
        #means return 200 response code   
        return ''
    elif request.method == 'GET':
        pass



@app.route('/live-inference')
def live_inference():
    my_data = inference_readings.query.order_by(inference_readings.datetime)
    return render_template('live-inference.html', my_data = my_data)



@app.route('/view-database')
def view_database():
    return render_template('view-database.html')


@app.route('/auxiliary-sensors')
def auxiliary_sensors():
    my_data_aux = auxiliary_sens.query.order_by(auxiliary_sens.datetime)
    return render_template('auxiliary-sensors.html', my_data_aux= my_data_aux)


@app.route('/about-project')
def about_project():
    return render_template('about-project.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
