# app.py
from flask import Flask, render_template, request, jsonify
import numpy as np
import sounddevice as sd
from scipy.signal import butter, sosfilt
import queue
import threading
import sounddevice as sd
import pyaudio
import sys
from threading import Lock
app = Flask(__name__)

        
# Global variables to store audio level safely
audio_level = {'rms': 0, 'peak': 0}
level_lock = Lock()

# Global state
audio_queue = queue.Queue(maxsize=10)
current_params = {
    'center_freq': 700,        # Hz
    'bandwidth': 250,          # Hz
    'sample_rate': 44100.0,    # Higher sample rate for better quality
    'buffer_size': 256,        # Smaller buffer size for lower latency
    'bit_depth': 24,           # Set to match audio interface
    'input_device_id': None,   # Will be set when input device is selected
    'output_device_id': None   # Will be set when output device is selected
}


def print_audio_debug_info():
    """Print detailed audio system information"""
    print("\n=== Sound Device Debug Info ===")
    try:
        print("\nSounddevice version:", sd.__version__)
        print("\nPortAudio version:", sd.get_portaudio_version())
        print("\nDefault devices:")
        print(f"Input: {sd.default.device[0]}")
        print(f"Output: {sd.default.device[1]}")
    except Exception as e:
        print("Error getting sounddevice info:", e)

    print("\n=== PyAudio Debug Info ===")
    try:
        p = pyaudio.PyAudio()
        print("\nPyAudio version:", pyaudio.__version__)
        print("\nAvailable devices:")
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            print(f"\nDevice {i}:")
            print(f"Name: {dev['name']}")
            print(f"Inputs: {dev['maxInputChannels']}")
            print(f"Outputs: {dev['maxOutputChannels']}")
            print(f"Default Sample Rate: {dev['defaultSampleRate']}")
        p.terminate()
    except Exception as e:
        print("Error getting PyAudio info:", e)

def get_audio_devices():
    """Get list of available audio devices using both sounddevice and PyAudio"""
    device_list = []
    
    try:
        print("\nTrying sounddevice...")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            device_list.append({
                'id': i,
                'name': device['name'],
                'inputs': device['max_input_channels'],
                'outputs': device['max_output_channels'],
                'default_samplerate': device['default_samplerate'],
                'backend': 'sounddevice'
            })
    except Exception as e:
        print(f"Sounddevice error: {e}")

    if not device_list:
        try:
            print("\nTrying PyAudio...")
            p = pyaudio.PyAudio()
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                device_list.append({
                    'id': i,
                    'name': dev['name'],
                    'inputs': dev['maxInputChannels'],
                    'outputs': dev['maxOutputChannels'],
                    'default_samplerate': dev['defaultSampleRate'],
                    'backend': 'pyaudio'
                })
            p.terminate()
        except Exception as e:
            print(f"PyAudio error: {e}")

    print(f"\nFound {len(device_list)} devices")
    for dev in device_list:
        print(f"Device: {dev['name']} (IN:{dev['inputs']}, OUT:{dev['outputs']})")
    
    return device_list

def create_bandpass_filter(center_freq, bandwidth, sample_rate):
    """Optimized bandpass filter balancing quality and latency"""
    center_freq = float(center_freq)
    bandwidth = float(bandwidth)
    sample_rate = float(sample_rate)
    
    low = center_freq - bandwidth/2
    high = center_freq + bandwidth/2
    nyquist = sample_rate / 2
    
    # Print debug info
    print(f"\nFilter Configuration:")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Center frequency: {center_freq} Hz")
    print(f"Bandwidth: {bandwidth} Hz")
    print(f"Passband: {low} Hz to {high} Hz")
    
    # Still using order 2, but optimized for lower latency
    order = 2
    return butter(order, Wn=[low/nyquist, high/nyquist], btype='band', output='sos')

def audio_callback(indata, outdata, frames, time, status):
    """Optimized callback for lower latency"""
    try:
        # Get the mono input and apply initial gain
        audio_data = indata[:, 0].astype(np.float32)
        
        # Print input levels only occasionally to reduce overhead
        if np.random.random() < 0.1:  # Only print 10% of the time
            input_peak = np.max(np.abs(audio_data))
            if input_peak > 0.01:
                   print(f"Input peak: {input_peak:.4f}, Buffer size: {current_params['buffer_size']} samples")
        
        # Initial gain stage
        pre_gain = 4.0
        audio_data = audio_data * pre_gain
        
        # Apply filter
        sos = create_bandpass_filter(
            current_params['center_freq'],
            current_params['bandwidth'],
            current_params['sample_rate']
        )
        filtered = sosfilt(sos, audio_data)
        
        # Final gain stage
        post_gain = 4.0
        filtered = filtered * post_gain
        
        # Fast limiter
        np.clip(filtered, -0.95, 0.95, out=filtered)
        
        outdata[:] = filtered.reshape(-1, 1)
        
    except Exception as e:
        print(f"Error in audio callback: {e}")
        outdata.fill(0)

def start_audio_stream(input_device_id, output_device_id, sample_rate=None, buffer_size=None):
    """Start audio stream with optimized latency settings"""
    if sample_rate is not None:
        current_params['sample_rate'] = float(sample_rate)
    
    if buffer_size is not None:
        current_params['buffer_size'] = buffer_size

    print(f"\nAudio Stream Configuration:")
    print(f"Sample rate: {current_params['sample_rate']} Hz")
    print(f"Buffer size: {current_params['buffer_size']} samples")
    
    try:
        stream = sd.Stream(
            device=(input_device_id, output_device_id),
            samplerate=current_params['sample_rate'],
            blocksize=current_params['buffer_size'],
            dtype=np.float32,
            channels=1,
            callback=audio_callback,
            latency='low'  # Changed to low latency
        )
        return stream
    except Exception as e:
        print(f"Error creating audio stream: {e}")
        return None

# Initialize audio stream (will be set when devices are selected)
audio_stream = None

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/get_devices')
def get_devices():
    """Get available audio devices"""
    try:
        devices = get_audio_devices()
        return jsonify({
            'status': 'success',
            'devices': devices
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/select_devices', methods=['POST'])
def select_devices():
    """Select input and output devices and initialize stream"""
    global audio_stream
    
    try:
        data = request.get_json()
        input_device_id = int(data['input_device_id'])
        output_device_id = int(data['output_device_id'])
        buffer_size = int(data.get('buffer_size', 256))
        
        # Stop existing stream if any
        if audio_stream is not None and audio_stream.active:
            audio_stream.stop()
        
        # Create new stream with selected devices
        audio_stream = start_audio_stream(
            input_device_id,
            output_device_id,
            buffer_size=buffer_size
        )
        
        if audio_stream is None:
            raise Exception("Failed to create audio stream")
        
        return jsonify({
            'status': 'success',
            'message': 'Devices selected successfully',
            'current_params': current_params
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/update_params', methods=['POST'])
def update_params():
    """Update filter parameters"""
    data = request.get_json()
    
    print(f"Received params update - Center: {data['center_freq']}, Bandwidth: {data['bandwidth']}")
    
    current_params['center_freq'] = max(20, min(20000, float(data['center_freq'])))
    current_params['bandwidth'] = max(1, min(current_params['center_freq'], float(data['bandwidth'])))
    
    print(f"Updated params - Center: {current_params['center_freq']}, Bandwidth: {current_params['bandwidth']}")
    
    return jsonify({
        'status': 'success',
        'params': current_params
    })


@app.route('/start', methods=['POST'])
def start_audio():
    """Start audio processing"""
    global audio_stream
    try:
        if audio_stream is None:
            return jsonify({
                'status': 'error',
                'message': 'No devices selected'
            })
        
        audio_stream.start()
        return jsonify({
            'status': 'success',
            'message': 'Audio started'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/stop', methods=['POST'])
def stop_audio():
    """Stop audio processing"""
    global audio_stream
    try:
        if audio_stream is not None:
            audio_stream.stop()
        return jsonify({
            'status': 'success',
            'message': 'Audio stopped'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/debug_audio')
def debug_audio():
    """Get audio system debug information"""
    try:
        print_audio_debug_info()
        return jsonify({
            'status': 'success',
            'message': 'Check server console for debug output'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)