"""Example 04: Mathematical Virtual Channels Engine.

Calculates derived torque, horsepower, fuel efficiency, and propeller slip.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from src.engine.virtual_channels.channel_engine import VirtualChannelEngine

def main():
    print("=== Verified Mathematical Virtual Channels ===")
    
    # 1. Engine Torque & Power
    rpm = 2100.0
    actual_torque_pct = 85.0
    nominal_torque = 1200.0  # Nm
    torque_nm, kw, hp = VirtualChannelEngine.calculate_torque_and_power(rpm, actual_torque_pct, nominal_torque)
    print(f"Motor: {rpm} RPM @ {actual_torque_pct}% Torque -> Torque: {torque_nm} Nm | Power: {kw} kW ({hp} HP)")

    # 2. Marine Fuel Efficiency (L/NM)
    fuel_lph = 42.5
    sog_knots = 24.0
    marine_eff = VirtualChannelEngine.calculate_marine_fuel_efficiency(fuel_lph, sog_knots)
    print(f"Marine Fuel Efficiency: {fuel_lph} L/h @ {sog_knots} Knots -> {marine_eff} L/NM")

    # 3. Propeller Slip %
    slip = VirtualChannelEngine.calculate_propeller_slip(
        engine_rpm=2400.0,
        gear_ratio=2.0,
        prop_pitch_inches=21.0,
        boat_speed_knots=18.5
    )
    print(f"Propeller Slip: {slip}%")

if __name__ == '__main__':
    main()
