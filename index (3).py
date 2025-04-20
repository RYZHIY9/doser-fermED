doser
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
#         Преобразование напряжения в pH.
#         """
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

pump sensor