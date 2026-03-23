import numpy as np # for calculations
import pandas as pd # for tables + CSV files
import random # for random

"""
Temperature: Measured in Celsius
Vibration: Measured in g's
RPM: Measured in Revolutions per Minute
Load: Measured in % of full capacity

Rules:
Sensor:	        Normal Range:	    Warning Range:	    Critical/Danger Range:
Temperature:	    60-75 Celsius	    75-82 Celsius	        >82 Celsius
Vibration:	        0.04-0.18 g's	    0.18-0.25 g's	        >0.25 gs
RPM:                1420-1480 RPM	    +-20 from base	        >1500 or <1380 RPM
Load:	            35-85%	            85-95%	                >95%

"""


# SIMULATION CONFIGURATION - REALISTIC INDUSTRIAL SCALE
NUM_MACHINES = 10  # 10 machines
DAYS_PER_CYCLE = 180  # ~6 months between major services
NUM_CYCLES = 10  # 10 cycles per machine of services (~6 mths).
OUTPUT_FILE = "bausch_and_lomb_style_sensor_data.csv"


class MachineBehavior:
    def __init__(self, machine_id): # Runs when creating a new machine

        # MACHINE IDENTITY & CHARACTERISTICS
        self.machine_id = machine_id # Give each machine a number (1,2,3...)

        # Machine lifecycle parameters (different per machine)
        self.age = np.random.uniform(0.1, 8.0)  # Years in service (0.1-8 years)
        self.quality = np.random.uniform(0.7, 1.0)  # Quality of the machines
        self.wear_resistance = np.random.uniform(0.5, 1.5)  # Wear resistence


        # HIDDEN DEGRADATION STATES
        self.bearing_wear = 0.0  # Bearing degradation (0=new, 1=failed)
        self.motor_degradation = 0.0  # Motor winding/insulation degradation
        self.thermal_stress = 0.0  # Cumulative thermal cycling damage
        self.lubrication_quality = 1.0  # Lubricant condition (1=perfect, 0=dry)


        # BASE OPERATING PARAMETERS
        self.base_temp = np.random.uniform(58, 68)  # Normal idle temperature (Celcius)
        self.base_vib = np.random.uniform(0.04, 0.12)  # Baseline vibration (g)
        self.base_rpm = np.random.uniform(1420, 1480)  # Nominal operating speed (RPM)


        # USAGE HISTORY & STRESS ACCUMULATION
        self.cycles_since_service = 0  # Cycles since last maintenance
        self.total_operating_hours = 0  # Cumulative runtime (hours)
        self.stress_accumulation = 0.0  # Combined mechanical/thermal stress


        # MAINTENANCE HISTORY & RELIABILITY FACTORS
        self.maintenance_quality = np.random.uniform(0.7, 1.0)  # Repair quality
        self.previous_failures = 0  # Historical failure count
        self.last_maintenance_effectiveness = 1.0  # How well last service worked

    def generate_load_pattern(self, day, cycle_day):

        # GENERATES REALISTIC PRODUCTION LOAD PATTERNS
        # Models: Weekly cycles, seasonal variations, monthly production targets

        # Calculate temporal patterns
        day_of_week = day % 7  # 0=Monday, 6=Sunday
        day_of_year = day % 365  # Seasonal indexing

        # Seasonal production variation (±10% annual cycle)
        seasonal_factor = 1.0 + 0.1 * np.sin(2 * np.pi * day_of_year / 365)

        # Weekly production schedule
        if day_of_week in [5, 6]:  # Weekend operation (lower load)
            base_load = np.random.normal(50, 5)  # Reduced weekend production
        else:  # Weekday operation (normal/high load)
            base_load = np.random.normal(68, 8)  # Standard weekday production

        # Monthly production cycles (start/end of month effects)
        if day % 30 < 5:  # First week of month - production surge
            base_load += np.random.uniform(10, 20)  # Rush to meet targets
        elif day % 30 > 25:  # Last week of month - production wind-down
            base_load -= np.random.uniform(5, 15)  # Reduced output

        # Apply seasonal adjustment
        base_load *= seasonal_factor

        # Random production anomalies (unplanned surges/downtime)
        if random.random() < 0.1:  # 10% chance of production surge
            base_load += np.random.uniform(15, 30)  # Emergency order/priority job
        elif random.random() < 0.08:  # 8% chance of low production day
            base_load -= np.random.uniform(10, 25)  # Material shortage/maintenance

        # Ensure load stays within operational limits (35%-98%)
        return max(35, min(98, base_load))

    def update_degradation(self, sensor_readings, day_in_cycle):

        # UPDATES HIDDEN DEGRADATION STATES BASED ON OPERATIONAL STRESS
        # Extract current sensor values
        temp, vibration, rpm, load = sensor_readings.values()

        # Age acceleration factor (older machines degrade faster)
        age_factor = min(2.0, 1.0 + (self.age / 10))

        # BEARING WEAR MECHANISM - Vibration and load dependent
        bearing_wear_rate = (vibration * 0.5 + load / 100 * 0.1) * (1 / self.wear_resistance)
        self.bearing_wear = min(1.0, self.bearing_wear + bearing_wear_rate * 0.001 * age_factor)

        # MOTOR DEGRADATION - RPM instability and thermal cycling
        rpm_variation = abs(rpm - self.base_rpm) / self.base_rpm  # Speed instability
        thermal_cycles = max(0, (temp - 65) / 20)  # Thermal stress
        self.motor_degradation = min(1.0, self.motor_degradation +
                                     (rpm_variation + thermal_cycles) * 0.0005)

        # LUBRICATION DEGRADATION - Temperature accelerated breakdown
        lubrication_degradation = 0.998 if temp > 75 else 0.9995  # Heat accelerates breakdown
        self.lubrication_quality = max(0.1, self.lubrication_quality * lubrication_degradation)

        # CUMULATIVE STRESS ACCUMULATION (fatigue damage model)
        daily_stress = (load / 100 * 0.1 + vibration * 0.5 + max(0, temp - 65) / 50)
        self.stress_accumulation += daily_stress

        # Track total operational runtime (24h continuous operation assumed)
        self.total_operating_hours += 24

    def calculate_sensor_readings(self, day_in_cycle, current_load):

        # CALCULATES SENSOR READINGS
        # Implements B+L supervisor's engineering relationships

        load_factor = current_load / 100.0  # Normalize load to 0-1 scale


        # SEASONAL TEMPERATURE EFFECTS (ambient temperature variation)
        day_of_year = day_in_cycle % 365
        seasonal_temp_effect = 3 * np.sin(2 * np.pi * day_of_year / 365)  # ±3 Celsius seasonal


        # TEMPERATURE CALCULATION
        temp_load_effect = load_factor * 8  # Base temperature increase with load

        # B+L Supervisor's pattern: "faster ramp above 70-80% load"
        if load_factor > 0.75:  # Critical load threshold
            temp_load_effect += (load_factor - 0.75) * 15  # Accelerated heating

        # Combine all temperature effects
        temperature = (self.base_temp + temp_load_effect +
                       self.bearing_wear * 3 +  # Bearing friction heat
                       (1 - self.lubrication_quality) * 8 +  # Poor lubrication heating
                       seasonal_temp_effect)  # Ambient variation


        # VIBRATION CALCULATION - B+L SUPERVISOR'S LOAD vs VIBRATION PATTERN
        vibration = (self.base_vib +
                     load_factor * 0.05 +  # "Gradual increase with load"
                     self.bearing_wear * 0.15 +  # Wear-induced vibration
                     self.motor_degradation * 0.1)  # Motor imbalance vibration

        # RPM STABILITY - B+L SUPERVISOR'S "TIGHT TO SETPOINT" PATTERN
        rpm_stability = 2 + self.motor_degradation * 5 + self.bearing_wear * 4
        rpm = self.base_rpm + np.random.normal(0, rpm_stability)  # Small normal fluctuations

        # RPM sag under high load for degraded machines
        if current_load > 80 and (self.motor_degradation > 0.3 or self.bearing_wear > 0.4):
            rpm -= (current_load - 80) * 0.4  # Load-induced speed drop

        # INTERMITTENT FAULT EFFECTS (pre-failure instability)
        if hasattr(self, 'intermittent_fault_active') and self.intermittent_fault_active:
            if random.random() < 0.6:  # 60% chance of vibration spike
                vibration *= random.uniform(1.1, 1.8)  # Temporary vibration increase
            if random.random() < 0.4:  # 40% chance of temperature spike
                temperature += random.uniform(1, 6)  # Temporary overheating
            if random.random() < 0.3:  # 30% chance of RPM fluctuation
                rpm += random.uniform(-10, 10)  # Temporary speed variation

        # REALISTIC SENSOR NOISE (measurement uncertainty)
        temperature += np.random.normal(0, 0.7)  # ±2 Celsius temperature noise
        vibration += np.random.normal(0, 0.012)  # ±0.036g vibration noise
        rpm += np.random.normal(0, 1.5)  # ±4.5 RPM speed noise

        # OCCASIONAL SENSOR ANOMALIES (transient measurement errors)
        if random.random() < 0.008:  # 0.8% chance of temperature sensor glitch
            temperature += np.random.uniform(3, 10)  # Significant temp spike
        if random.random() < 0.006:  # 0.6% chance of vibration sensor glitch
            vibration += np.random.uniform(0.05, 0.15)  # Significant vibration spike

        # RETURN PHYSICALLY-CONSTRAINED SENSOR READINGS
        return {
            'temperature': max(40, min(95, round(temperature, 2))),  # 40-95 Celsius range
            'vibration': max(0.02, min(0.5, round(vibration, 4))),  # 0.02-0.5g range
            'rpm': max(1380, round(rpm, 1)),  # Min 1380 RPM
            'load': round(current_load, 1)  # 35-98% load
        }

    def check_failure_risk(self, sensor_readings, day_in_cycle):

        # CALCULATES FAILURE RISK FROM CURRENT STATE AND SENSOR PATTERNS
        # Implements multiple failure modes based on supervisor's guidance
        temp, vibration, rpm, load = sensor_readings.values()

        # Age-dependent risk multiplier (older = higher baseline risk)
        age_risk_factor = min(2.0, 1.0 + (self.age / 15))

        failure_risk = 0  # Initialize overall risk

        # FAILURE MODE 1: BEARING FAILURE (Vibration-driven)
        bearing_risk = 0
        if vibration > 0.18 and self.bearing_wear > 0.5:  # High vib + existing wear
            bearing_risk = 0.6
        elif vibration > 0.25:  # Critical vibration level
            bearing_risk = 0.8
        elif self.bearing_wear > 0.8:  # Advanced bearing wear
            bearing_risk = 0.7

        # FAILURE MODE 2: MOTOR OVERHEATING (Temperature-driven)
        motor_risk = 0
        if temp > 78 and rpm > self.base_rpm + 20:  # Overheat + overspeed
            motor_risk = 0.5
        elif temp > 82:  # Critical temperature
            motor_risk = 0.7
        elif self.motor_degradation > 0.6 and temp > 70:  # Degraded motor running hot
            motor_risk = 0.4

        # FAILURE MODE 3: LUBRICATION FAILURE (Oil breakdown)
        lubrication_risk = 0
        if self.lubrication_quality < 0.3 and temp > 70:  # Poor lubrication + heat
            lubrication_risk = 0.5
        elif self.lubrication_quality < 0.1:  # Critical lubrication failure
            lubrication_risk = 0.8

        # FAILURE MODE 4: CUMULATIVE STRESS FAILURE (Fatigue)
        stress_risk = 0
        if self.stress_accumulation > 30 and day_in_cycle > 100:  # High cumulative stress
            stress_risk = min(0.6, self.stress_accumulation / 60)  # Scale with stress

        # FAILURE MODE 5: COMBINED DEGRADATION (Multiple issues)
        combined_risk = 0
        degradation_score = (self.bearing_wear + self.motor_degradation +
                             (1 - self.lubrication_quality))  # Combined degradation
        if degradation_score > 1.2 and load > 70:  # Multiple issues under high load
            combined_risk = min(0.9, degradation_score / 2.0)


        # AGE-RELATED FAILURE RISK (General wear-out)
        age_risk = min(0.3, (self.age - 5) * 0.06) if self.age > 5 else 0

        # COMBINE FAILURE RISKS (Probability union)
        risks = [bearing_risk, motor_risk, lubrication_risk, stress_risk, combined_risk, age_risk]
        failure_risk = 1 - np.prod([1 - r for r in risks])  # Combined probability

        # Apply age acceleration factor
        failure_risk *= age_risk_factor

        # INTERMITTENT FAULT ACTIVATION (Early warning signs)
        if not hasattr(self, 'intermittent_fault_active'):
            self.intermittent_fault_active = False

        # Activate intermittent faults when risk becomes significant
        if failure_risk > 0.4 and not self.intermittent_fault_active:
            if random.random() < 0.3:  # 30% chance to start intermittent faults
                self.intermittent_fault_active = True

        # CRITICAL FAILURE CONDITIONS (Immediate failure)
        if (temp > 85 or vibration > 0.35 or
                self.bearing_wear > 0.95 or self.lubrication_quality < 0.05):
            failure_risk = 1.0  # Guaranteed failure

        # RANDOM COMPONENT FAILURES (Unpredictable events)
        if random.random() < 0.0002:  # 0.02% daily chance of random failure
            failure_risk = 1.0

        return min(1.0, failure_risk)  # Cap at 100%

    def apply_maintenance(self):

        # APPLIES MAINTENANCE EFFECTS - RESETS DEGRADATION STATES
        # Models real-world maintenance effectiveness and partial repairs
        # Calculate maintenance effectiveness (quality × random workmanship)
        effectiveness = self.maintenance_quality * random.uniform(0.8, 1.0)
        self.last_maintenance_effectiveness = effectiveness

        # DEGRADATION RESET WITH MAINTENANCE EFFECTIVENESS
        self.bearing_wear *= (0.2 + 0.5 * (1 - effectiveness))  # Bearing repair
        self.motor_degradation *= (0.3 + 0.5 * (1 - effectiveness))  # Motor service
        self.lubrication_quality = min(1.0, self.lubrication_quality + 0.6 * effectiveness)  # Relubrication
        self.stress_accumulation *= (0.1 + 0.3 * (1 - effectiveness))  # Stress relief

        # Reset intermittent fault state (maintenance fixes intermittent issues)
        self.intermittent_fault_active = False


# MAIN DATA GENERATION LOOP
rows = []
machines = [MachineBehavior(i) for i in range(1, NUM_MACHINES + 1)]

# Simulate multiple operational cycles
for cycle in range(1, NUM_CYCLES + 1):
    for machine in machines:
        # Apply maintenance at start of each new cycle (except first)
        if cycle > 1:
            machine.apply_maintenance()
        machine.cycles_since_service += 1

        # Cycle-level failure tracking
        failure_occurred = False
        consecutive_high_risk_days = 0
        intermittent_fault_days = 0

        # Daily operation simulation
        for day_in_cycle in range(1, DAYS_PER_CYCLE + 1):
            global_day = (cycle - 1) * DAYS_PER_CYCLE + day_in_cycle

            #  Generate daily operating conditions
            current_load = machine.generate_load_pattern(global_day, day_in_cycle)
            sensor_readings = machine.calculate_sensor_readings(day_in_cycle, current_load)
            machine.update_degradation(sensor_readings, day_in_cycle)
            failure_risk = machine.check_failure_risk(sensor_readings, day_in_cycle)

            # Track failure progression patterns
            if failure_risk > 0.6:
                consecutive_high_risk_days += 1  # Count high-risk days
            else:
                consecutive_high_risk_days = 0  # Reset counter

            # Track intermittent fault duration
            if hasattr(machine, 'intermittent_fault_active') and machine.intermittent_fault_active:
                intermittent_fault_days += 1
            else:
                intermittent_fault_days = 0

            # Determine if failure occurs today
            failure_event = 0
            if not failure_occurred:
                # Risk multipliers for prolonged high-risk conditions
                probability_multiplier = 1.0 + (consecutive_high_risk_days * 0.2)
                if intermittent_fault_days > 5:  # Extended intermittent faults
                    probability_multiplier *= 1.5

                effective_risk = failure_risk * probability_multiplier

                # Failure determination logic
                if effective_risk > 0.85:  # Very high risk → guaranteed failure
                    failure_event = 1
                    failure_occurred = True
                    machine.previous_failures += 1
                elif random.random() < effective_risk * 0.1:  # Probabilistic failure
                    failure_event = 1
                    failure_occurred = True
                    machine.previous_failures += 1

            # Service flag (maintenance occurred at cycle start)
            service_flag = 1 if (day_in_cycle == 1 and cycle > 1) else 0

            # Record daily data point
            rows.append({
                "machine_id": machine.machine_id,
                "cycle": cycle,
                "day": global_day,
                "day_in_cycle": day_in_cycle,
                "temperature": sensor_readings['temperature'],
                "vibration": sensor_readings['vibration'],
                "rpm": sensor_readings['rpm'],
                "load": sensor_readings['load'],
                "service_flag": service_flag,
                "failure_event": failure_event
            })


# Create final dataset + make the CSV
df = pd.DataFrame(rows)
df.to_csv(OUTPUT_FILE, index=False)

