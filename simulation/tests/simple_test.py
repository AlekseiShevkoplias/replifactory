import pytest
import numpy as np
from replifactory_core.base_device import BaseDeviceConfig
from replifactory_simulation.simulation_factory import create_simulated_device
from replifactory_core.interfaces import DeviceError, StirrerSpeed


@pytest.fixture
def device():
    return create_simulated_device()


def test_device_creation():
    device = create_simulated_device()
    assert device is not None
    
    # Check required components exist
    assert 1 in device._pumps  # Media pump
    assert 2 in device._pumps  # Drug pump
    assert 4 in device._pumps  # Waste pump
    assert device._valves is not None
    assert device._stirrer is not None
    assert device._od_sensor is not None
    assert device._thermometer is not None


def test_vial_measurements(device):
    # Test valid measurement
    measurements = device.measure_vial(1)
    assert measurements.od >= 0
    assert 20 <= measurements.temperature <= 45  # Reasonable temp range
    assert measurements.rpm is not None
    
    # Test invalid vial number
    with pytest.raises(ValueError):
        device.measure_vial(8)
    with pytest.raises(ValueError):
        device.measure_vial(0)


def test_dilution_operation(device):
    # Valid dilution
    device.make_dilution(1, media_volume=5.0, drug_volume=0.5)
    
    # Test volume limits
    with pytest.raises(ValueError):
        device.make_dilution(1, media_volume=50.0, drug_volume=0.5)  # Too much volume
        
    # Test invalid vial
    with pytest.raises(ValueError):
        device.make_dilution(8, media_volume=5.0, drug_volume=0.5)


def test_pump_behavior(device):
    pump = device._pumps[1]
    
    # Test pumping
    initial_volume = pump.pumped_volume
    test_volume = 5.0
    pump.pump(test_volume)
    assert pump.pumped_volume == initial_volume + test_volume
    assert not pump.is_pumping
    
    # Test concurrent pumping prevention
    with pytest.raises(DeviceError):
        pump.pump(1.0)
        pump.pump(1.0)  # Should fail - pump busy


def test_valve_operations(device):
    valves = device._valves
    
    # Test open/close
    valves.open(1)
    assert valves.is_open(1)
    valves.close(1)
    assert not valves.is_open(1)
    
    # Test close_all
    valves.open(1)
    valves.open(2)
    valves.close_all()
    assert not any(valves.is_open(v) for v in range(1, 8))


def test_stirrer_control(device):
    stirrer = device._stirrer
    
    # Test speed setting
    stirrer.set_speed(1, StirrerSpeed.HIGH)
    rpm = stirrer.measure_rpm(1)
    assert rpm > 0
    
    stirrer.set_speed(1, StirrerSpeed.STOPPED)
    rpm = stirrer.measure_rpm(1)
    assert rpm == 0
    
    # Test emergency stop
    stirrer.set_speed(1, StirrerSpeed.HIGH)
    stirrer.stop_all()
    rpm = stirrer.measure_rpm(1)
    assert rpm == 0


def test_od_sensor(device):
    sensor = device._od_sensor
    
    # Test OD measurement
    od, signal = sensor.measure_od(1)
    assert od >= 0
    assert signal > 0
    
    # Test blank measurement
    blank = sensor.measure_blank(1)
    assert blank > 0


def test_temperature_monitoring(device):
    temps = device._thermometer.measure_temperature()
    
    assert 'vials' in temps
    assert 'board' in temps
    assert 20 <= temps['vials'] <= 45
    assert 20 <= temps['board'] <= 45


def test_vial_status(device):
    status = device.vial_status
    
    # Check all vials present
    assert all(v in status for v in range(1, 8))
    
    # Check required measurements
    for v in range(1, 8):
        assert 'od' in status[v]
        assert 'temperature' in status[v]
        assert 'rpm' in status[v]


def test_emergency_stop(device):
    # Set up some activity
    device._valves.open(1)
    device._stirrer.set_speed(1, StirrerSpeed.HIGH)
    
    # Emergency stop
    device.emergency_stop()
    
    # Verify everything stopped
    assert not device._valves.is_open(1)
    assert device._stirrer.measure_rpm(1) == 0
    assert not any(pump.is_pumping for pump in device._pumps.values())


def test_growth_simulation(device):
    # Initial measurement
    m1 = device.measure_vial(1)
    initial_od = m1.od
    
    # Make dilution and verify OD decreases
    device.make_dilution(1, media_volume=5.0, drug_volume=0.0)
    m2 = device.measure_vial(1)
    assert m2.od < initial_od
    
    # Add drug and verify growth impact
    device.make_dilution(1, media_volume=0.0, drug_volume=5.0)
    m3 = device.measure_vial(1)
    status = device.vial_status