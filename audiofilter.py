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
    'sample_rate': 48000,      # Higher sample rate for better quality
    'buffer_size': 256,        # Smaller buffer size for lower latency
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
    """Create a bandpass filter using scipy's butter filter"""
    low = center_freq - bandwidth/2
    high = center_freq + bandwidth/2
    nyquist = sample_rate / 2
    
    print(f"Filter params - Center: {center_freq}, Bandwidth: {bandwidth}")
    print(f"Pre-normalize - Low: {low}, High: {high}, Nyquist: {nyquist}")
    
    # Remove the max(20, ...) clamp when normalizing
    low_norm = low / nyquist
    high_norm = high / nyquist
    
    # Ensure the normalized frequencies are within (0, 1)
    low_norm = max(0.001, min(0.99, low_norm))
    high_norm = max(0.001, min(0.99, high_norm))
    
    print(f"Normalized - Low: {low_norm}, High: {high_norm}")
    
    order = 2
    return butter(order, [low_norm, high_norm], btype='band', output='sos')

def audio_callback(indata, outdata, frames, time, status):
    """Optimized callback function for CW audio filtering"""
    try:
        # Convert input to float32 and normalize
        audio_data = indata[:, 0].astype(np.float32)
        
        # Add input level monitoring
        input_max = np.max(np.abs(audio_data))
        if input_max > 0.01:  # Only print when signal is present
            print(f"Input level: {input_max}")
        
        # Normalize input if it's too hot
        if input_max > 0:
            audio_data = audio_data / (input_max + 1e-6)  # Prevent divide by zero
        
        # Get filter parameters
        center_freq = current_params['center_freq']
        bandwidth = current_params['bandwidth']
        sample_rate = current_params['sample_rate']
        
        # Apply the bandpass filter
        sos = create_bandpass_filter(center_freq, bandwidth, sample_rate)
        filtered = sosfilt(sos, audio_data)
        
        # Apply a very modest gain
        gain = 0.7  # Reduced gain to prevent clipping
        filtered = filtered * gain
        
        # Gentle compression instead of hard clipping
        threshold = 0.7
        if np.max(np.abs(filtered)) > threshold:
            filtered = np.sign(filtered) * (threshold + (np.abs(filtered) - threshold) * 0.3)
        
        # Monitor output levels
        output_max = np.max(np.abs(filtered))
        if output_max > 0.01:
            print(f"Output level: {output_max}")
            
        outdata[:] = filtered.reshape(-1, 1)
        
    except Exception as e:
        print(f"Error in audio callback: {e}")
        outdata.fill(0)



    
def start_audio_stream(input_device_id, output_device_id, sample_rate=None, buffer_size=None):
    """Initialize and start the audio stream with specified parameters"""
    if sample_rate is not None:
        current_params['sample_rate'] = sample_rate
    
    if buffer_size is not None:
        current_params['buffer_size'] = buffer_size

    current_params['input_device_id'] = input_device_id
    current_params['output_device_id'] = output_device_id

    try:
        # Create stream with separate input and output devices
        stream = sd.Stream(
            device=(input_device_id, output_device_id),  # Separate input and output devices
            samplerate=current_params['sample_rate'],
            blocksize=current_params['buffer_size'],
            dtype=np.float32,
            channels=1,
            callback=audio_callback,
            latency='low'
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