#!/usr/bin/env python
import json
import threading
import RPi.GPIO as GPIO
import serial
import time
import struct
import adafruit_dht
import board

from http.server import BaseHTTPRequestHandler, HTTPServer
from jinja2 import Template

# flask
#from flask import Flask, render_template, request, jsonify, make_response

# doser_sensor
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import math


one = 26
two = 20
three = 21
pumpPinLower = 12
pumpPinUpper = 27


# Устанавливаем аналоговый вход как вход


GPIO.setmode(GPIO.BCM)
#Setting GPIO

GPIO.setwarnings(False)
GPIO.setup(three,GPIO.OUT)
GPIO.setup(two,GPIO.OUT)
GPIO.setup(one,GPIO.OUT)
GPIO.setup(pumpPinLower,GPIO.OUT)
GPIO.setup(pumpPinUpper,GPIO.OUT)


GPIO.output(pumpPinLower, 1)
GPIO.output(pumpPinUpper, 1)

GPIO.output(one, 1)
GPIO.output(two, 1)
GPIO.output(three, 1)


def init_rele1():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(one, GPIO.OUT)

def init_rele2():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(two, GPIO.OUT)

def init_rele3():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(three, GPIO.OUT)

# Initialize GPIO pins before starting threads
init_rele1()
init_rele2()
init_rele3()

def rasperrypi_pinout(pin: int, value: bool):
    print("Включенно" if value else "Выключенно")
    GPIO.output(pin, value)

def rasperrypi_cleanup():
    GPIO.cleanup()


# mx-z19b
ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate=9600,
    timeout=5
)
k=struct.pack('B', 0xff)

ser = serial.Serial(port="/dev/ttyS1",baudrate =9600)

def text21(str):
    command = 't6.txt="' + str + '"'
    ser.write(command.encode())
    ser.write(k)
    ser.write(k)
    ser.write(k)
def text1(str):
    command = 't7.txt="' + str + '"'
    ser.write(command.encode())
    ser.write(k)
    ser.write(k)
    ser.write(k)
def text2(str):
    command = 't8.txt="' + str + '"'
    ser.write(command.encode())
    ser.write(k)
    ser.write(k)
    ser.write(k)
def text3(str):
    command = 't9.txt="' + str + '"'
    ser.write(command.encode())
    ser.write(k)
    ser.write(k)
    ser.write(k)


time.sleep(2)
print("Ферма готова к работе!")


# mx-z19b
co2 = ''

def read_co2(serial_port):
    # Отправляем команду для чтения данных
    serial_port.write(b'\xff\x01\x86\x00\x00\x00\x00\x00\x79')
    time.sleep(0.1)
    
    # Читаем 9 байт данных
    response = serial_port.read(9)
    
    # Проверка корректности данных
    if len(response) == 9 and response[0] == 0xff and response[1] == 0x86:
        high = response[2]
        low = response[3]
        co2 = (high << 8) + low
        return co2
    else:
        return None

def run_co2():
    global ser
    global co2
    try:
        while True:
            co2_value = read_co2(ser)
            if co2_value:
                print(f"CO2 Concentration: {co2_value} ppm")
                co2 = co2_value
            time.sleep(3)
    except KeyboardInterrupt:
        print("Program interrupted by user.")
    finally:
        ser.close()

def run_co2_thread():
    t = threading.Thread(target=run_co2, args=())
    t.start()
run_co2_thread()


# doser
ph = ''
ec = ''
tds = '' 
waterTemp = ''

class Doser:
    # Создаем I2C-шину
    i2c = busio.I2C(board.SCL, board.SDA)

    # Создаем объект ADS1115
    ads = ADS.ADS1115(i2c)

    # Настройка каналов для считывания
    chan_ph = AnalogIn(ads, ADS.P0)
    chan_temp = AnalogIn(ads, ADS.P1)
    chan_ec = AnalogIn(ads, ADS.P2)
    chan_tds = AnalogIn(ads, ADS.P3)

    # Калибровочные значения для преобразования напряжения в pH
    neutral_voltage = 2.5  # напряжение при pH 7.0
    voltage_per_pH = 0.15  # напряжение на одну единицу pH (примерное значение)

    @staticmethod
    def voltage_to_ph(voltage, neutral_voltage, voltage_per_pH):
        """
        Преобразование напряжения в pH.
        """
        return  (voltage - neutral_voltage) / voltage_per_pH

    # Константы для преобразования напряжения в температуру (для термистора NCP)
    R_nominal = 10000.0  # номинальное сопротивление термистора при 25°C
    T_nominal = 25.0  # номинальная температура в градусах Цельсия
    B_coefficient = 3950.0  # коэффициент B-значения термистора
    R_series = 10000.0  # сопротивление в делителе напряжения
    
    @staticmethod
    def voltage_to_temperature(voltage):
        """
        Преобразование напряжения в температуру для термистора NCP.
        """
       
        # Применяем уравнение Штеинхарта-Харта
        try:
            resistance = Doser.R_series * (3.3 / voltage - 1.0)
            steinhart = resistance / Doser.R_nominal  # (R/Ro)
            steinhart /= Doser.B_coefficient  # 1/B * ln(R/Ro)
            steinhart += 1.0 / (Doser.T_nominal + 273.15)  # + (1/To)
            steinhart = 1.0 / steinhart  # Invert
            steinhart -= 273.15  # Convert to Celsius
        except ValueError as e:
            print(f"Error in temperature calculation: {e}")
            return float('nan')
        return steinhart

    # Калибровочные данные для преобразования напряжения в EC и TDS
    # Примеры калибровочных данных:
    # EC: 3000 µS/cm при 2.0 В и 1000 µS/cm при 1.0 В
    # TDS: 1200 ppm при 2.0 В и 500 ppm при 1.0 В

    # Рассчитываем коэффициенты для EC
    ec_4000_voltage = 4
    ec_1000_voltage = 1.0  # Напряжение при 1000 µS/cm
    ec_slope = (3000 - 1000) / ec_4000_voltage - ec_1000_voltage 
    ec_intercept = 3000 - (ec_slope * ec_4000_voltage)

    # Рассчитываем коэффициенты для TDS
    tds_1200_voltage = 2.0  # Напряжение при 1200 ppm
    tds_500_voltage = 1.0  # Напряжение при 500 ppm
    tds_slope = (1200 - 500) / (tds_1200_voltage - tds_500_voltage)
    tds_intercept = 1200 - (tds_slope * tds_1200_voltage)
    
    @staticmethod
    def voltage_to_ec(voltage):
        """
        Преобразование напряжения в EC.
        """
        return Doser.ec_slope * voltage + Doser.ec_intercept

    @staticmethod
    def voltage_to_tds(voltage):
        """
        Преобразование напряжения в TDS.
        """
        return Doser.tds_slope * voltage + Doser.tds_intercept
    
    @staticmethod
    def run():
        global ph
        global waterTemp
        global ec
        global tds
        
        while True:
            values_ph = []
            values_temp = []
            values_ec = []
            values_tds = []
            try:
                while len(values_ph) < 25:
                    # Читаем значение напряжения с датчиков
                    voltage_ph = Doser.chan_ph.voltage
                    voltage_temp = Doser.chan_temp.voltage
                    voltage_ec = Doser.chan_ec.voltage
                    voltage_tds = Doser.chan_tds.voltage

                    # Преобразуем напряжение в значения pH, температуры, EC и TDS
                    ph_value = Doser.voltage_to_ph(voltage_ph, Doser.neutral_voltage, Doser.voltage_per_pH)
                    temp_value = Doser.voltage_to_temperature(voltage_temp)
                    ec_value = Doser.voltage_to_ec(voltage_ec)
                    tds_value = Doser.voltage_to_tds(voltage_tds)

                    # Сохраняем значения для усреднения
                    if ph_value > 0:
                        values_ph.append(ph_value)
                        values_temp.append(temp_value)
                        values_ec.append(ec_value)
                        values_tds.append(tds_value)

                    # Ждем 0.2 секунды перед следующим измерением
                    time.sleep(0.2)

            except KeyboardInterrupt:
                print("Program stopped by User")
            finally:
                print("Cleanup")
            
            # Выводим усредненные значения в консоль
            if values_ph:
                avg_ph = sum(values_ph) / len(values_ph)
            else:
                avg_ph = float('nan')

            if values_temp:
                avg_temp = sum(values_temp) / len(values_temp)
            else:
                avg_temp = float('nan')

            if values_ec:
                avg_ec = sum(values_ec) / len(values_ec)
            else:
                avg_ec = float('nan')

            if values_tds:
                avg_tds = sum(values_tds) / len(values_tds)
            else:
                avg_tds = float('nan')
            
            
            
            
            ph = f"{avg_ph:.2f}"
            ec = f"{avg_ec:.2f}"
            tds = f"{avg_tds:.2f}"
            waterTemp = f"{avg_temp:.2f}"
            
            print(f"PH Value: {avg_ph:.2f}")
            print(f"Temperature: {avg_temp:.2f} °C")
            print(f"EC Value: {avg_ec:.2f} µS/cm")
            print(f"TDS Value: {avg_tds:.2f} ppm")

            # Ждем 1 секунду перед следующим циклом
            time.sleep(2)

def run_doser_thread():
    doserStart = threading.Thread(target=Doser.run, args=())
    doserStart.start()
run_doser_thread()



# autodoser ph
def run_doser_ph():
    while True:
        if ph != '' and float(ph) > 7:
            rasperrypi_pinout(two, False)
            time.sleep(7)
            rasperrypi_pinout(two, True)
            time.sleep(5*60)
           
        time.sleep(5)

def run_doser_ph_thread():
    autodoserStart = threading.Thread(target=run_doser_ph, args=())
    autodoserStart.start()
run_doser_ph_thread()

# autodoser ec
def run_doser_ec():
    while True:
        if  ec != '' and float(ec) > 2000:
            rasperrypi_pinout(two, False)
            time.sleep(7)
            rasperrypi_pinout(two, True)
            time.sleep(5*60)
           
        time.sleep(5)

def run_doser_ec_thread():
    autodoserStart = threading.Thread(target=run_doser_ec, args=())
    autodoserStart.start()
run_doser_ec_thread()

#autodoser tds

def run_doser_tds():
    while True:
        if tds != '' and float(tds) > 1000:
            rasperrypi_pinout(two, False)
            time.sleep(7)
            rasperrypi_pinout(two, True)
            time.sleep(5*60)
           
        time.sleep(5)

def run_doser_tds_thread():
    autodoserStart = threading.Thread(target=run_doser_tds, args=())
    autodoserStart.start()
run_doser_tds_thread()

# pump sensor
water = ''

def pump():
    pumpStart = threading.Timer(2.0, doPump)
    pumpStart.start()
def doPump():
    global water
    
    if GPIO.input(pumpPinLower) and GPIO.input(pumpPinUpper):
        water = 'воды нет'
        print('воды нет')
    elif not GPIO.input(pumpPinLower) and not GPIO.input(pumpPinUpper) :
        water = 'воды достаточно'
        print('воды достаточно')
    elif not GPIO.input(pumpPinLower):
        water = 'воды мало'
        print('воды мало')
    pump()
pump()


# dht sensor
temp = ''
vlash = ''

def dht():
    dhtStart = threading.Timer(2.0, doDht)
    dhtStart.start()
def doDht():
    dhtPin = board.D18 
    dht_sensor = adafruit_dht.DHT22(dhtPin)
    GPIO.setmode(GPIO.BCM)
    try:
        global temp
        global vlash
        temp = str(dht_sensor.temperature)
        vlash = str(dht_sensor.humidity)
        text21(("{} C ".format(temperature_c)))
        text1(("{} % ".format(humidity)))
        print(f'Temperature: {dht_sensor.temperature:.2f}°C, Humidity: {dht_sensor.humidity:.2f}%')
    except RuntimeError as e:
        print(e)
    except KeyboardInterrupt:
        print('Program stopped by the user.')
    finally:
        dht_sensor.exit()
    dht()
dht()


# web server
class ServerHandler(BaseHTTPRequestHandler):
    def render_index(self):
        global temp, vlash, co2, ph, ec, tds, waterTemp, water
        
        with open("./index.html", "r", encoding="utf-8") as file:
            html = file.read()

        template = Template(html)
        return template.render(temp = temp, vlash = vlash, co2 = co2, ph = ph, water = water, ec = ec, tds = tds, waterTemp = waterTemp)

    def do_GET(self):
        print("GET request, path:", self.path)
        if self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = self.render_index()
            self.wfile.write(html.encode('utf-8'))
        elif self.path.startswith("/sensors/"):
            sensor = self.path.split('/')[-1]
            value = globals().get(sensor)
            if value is not None:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({sensor: value}).encode('utf-8'))
            else:
                self.send_error(404, "Sensor not found {}".format(sensor))
        else:
            self.send_error(404, "Page Not Found {}".format(self.path))
            
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        try:
            print("POST request, path:", self.path, "body:", body.decode('utf-8'))
            if self.path == "/led1":
                data_dict = json.loads(body.decode('utf-8'))
                if 'on' in data_dict:
                    rasperrypi_pinout(one, data_dict['on'])
                    
            elif self.path == "/led2":
                data_dict = json.loads(body.decode('utf-8'))
                if 'on' in data_dict:
                    rasperrypi_pinout(two, data_dict['on'])
                    
            elif self.path == "/led3":
                data_dict = json.loads(body.decode('utf-8'))
                if 'on' in data_dict:
                    rasperrypi_pinout(three, data_dict['on'])

                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"OK")
                
            else:
                self.send_response(400, 'Bad Request: Method does not exist')
                self.send_header('Content-Type', 'application/json')
                self.end_headers()

        except Exception as err:
            print("do_POST exception: %s" % str(err))

def server_thread(PORT):
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, ServerHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        exit(0)
    finally:
        httpd.server_close()




# entrypoint
if __name__ == '__main__':
    PORT = 4242
    print(f"Стартовал сервер с портом: {PORT}")
    server_thread(PORT)


while True:
    received_data = ser.read()              #read serial port
    time.sleep(0.03)
    data_left = ser.inWaiting()             #check for remaining byte
    received_data += ser.read(data_left)
    #print(received_data) #print received data
    ser.write(received_data)    
    try:
        output = received_data
        if output:
            if output == b'rele2\r':
                print("Не найден №1")
                if tombol1_sts==False:
                    print("Реле №1 включено")
                    #turn on relay1
                    GPIO.output(two, 0)
                    tombol1_sts = True
                else:
                    GPIO.output(two, 1)
                    print("Реле №1 выключено")
                    tombol1_sts = False
                    
            if output == b'rele3\r':
                print("Не найден №2")
                if tombol2_sts==False:
                    print("Реле №2 включено")
                    #turn on relay2
                    GPIO.output(one, 0)
                    tombol2_sts = True
                else:
                    GPIO.output(one, 1)
                    print("Реле №2 выключено")
                    tombol2_sts = False
            
            if output == b'rele1\r':
                print("Не найден №3")
                if tombol3_sts==False:
                    print("Реле №3 включено")
                    #turn on relay3
                    GPIO.output(three, 0)
                    tombol3_sts = True
                else:
                    GPIO.output(three, 1)
                    print("Реле №3 выключено")
                    tombol3_sts = False
            if output == b'off\x0b':
                    GPIO.output(one, 1)
                    GPIO.output(two, 1)
                    GPIO.output(three, 1)
                    print("Все реле выключены")
                    tombol1_sts = False
                    tombol2_sts = False
                    tombol3_sts = False
            if output == b'time1\r':
                print("Таймер включён")
                GPIO.output(one,0)
                time.sleep(3)
                GPIO.output(one,1)
                print("Таймер выключён")
    except RuntimeError as error:
        print(error.args[0])
        time.sleep(2.0)
        continue
    except Exception as error:
        dhtDevice.exit()
        raise error
        pass