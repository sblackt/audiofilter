# app.py
from flask import Flask, render_template, request, jsonify
import numpy as np
import sounddevice as sd
from scipy.signal import butter, sosfilt
import queue
import threading
# Add these imports at the top
import sounddevice as sd
import pyaudio
import sys

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

app = Flask(__name__)

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
# Global state
audio_queue = queue.Queue(maxsize=10)
current_params = {
    'center_freq': 700,    # Hz
    'bandwidth': 250,      # Hz
    'sample_rate': 48000,  # Higher sample rate for better quality
    'buffer_size': 256,    # Smaller buffer size for lower latency
    'device_id': None      # Will be set when device is selected
}

def get_audio_devices():
    """Get list of available audio devices using both sounddevice and PyAudio"""
    device_list = []
    
    # Try sounddevice first
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

    # Try PyAudio if sounddevice failed or found no devices
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
    low = max(20, min(low / nyquist, 0.99))  # Prevent frequencies too close to 0 or Nyquist
    high = max(20, min(high / nyquist, 0.99))
    
    # Use order 2 for lower latency while maintaining decent quality
    order = 2
    return butter(order, [low, high], btype='band', output='sos')

def audio_callback(indata, outdata, frames, time, status):
    """Optimized callback function for audio processing"""
    if status:
        print(status)
    
    try:
        # Process audio in float32 for better performance
        audio_data = indata[:, 0].astype(np.float32)
        
        # Get current filter parameters
        center_freq = current_params['center_freq']
        bandwidth = current_params['bandwidth']
        sample_rate = current_params['sample_rate']
        
        # Create and apply the filter
        sos = create_bandpass_filter(center_freq, bandwidth, sample_rate)
        filtered = sosfilt(sos, audio_data)
        
        # Apply to all output channels
        outdata[:] = filtered.reshape(-1, 1)
        
    except Exception as e:
        print(f"Error in audio callback: {e}")
        outdata.fill(0)

def start_audio_stream(device_id=None, sample_rate=None, buffer_size=None):
    """Initialize and start the audio stream with specified parameters"""
    if device_id is not None:
        current_params['device_id'] = device_id
    
    if sample_rate is not None:
        current_params['sample_rate'] = sample_rate
    
    if buffer_size is not None:
        current_params['buffer_size'] = buffer_size

    try:
        # Create stream with optimized settings
        stream = sd.Stream(
            device=(device_id, device_id),  # Same device for input and output
            samplerate=current_params['sample_rate'],
            blocksize=current_params['buffer_size'],
            dtype=np.float32,  # Use float32 for better performance
            channels=1,
            callback=audio_callback,
            latency='low'  # Request low latency mode
        )
        return stream
    except Exception as e:
        print(f"Error creating audio stream: {e}")
        return None

# Initialize audio stream (will be set when device is selected)
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

@app.route('/select_device', methods=['POST'])
def select_device():
    """Select audio device and initialize stream"""
    global audio_stream
    
    try:
        data = request.get_json()
        device_id = int(data['device_id'])
        sample_rate = float(data.get('sample_rate', 48000))
        buffer_size = int(data.get('buffer_size', 256))
        
        # Stop existing stream if any
        if audio_stream is not None and audio_stream.active:
            audio_stream.stop()
        
        # Create new stream with selected device
        audio_stream = start_audio_stream(device_id, sample_rate, buffer_size)
        
        if audio_stream is None:
            raise Exception("Failed to create audio stream")
        
        return jsonify({
            'status': 'success',
            'message': 'Device selected successfully',
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
    
    current_params['center_freq'] = max(20, min(20000, float(data['center_freq'])))
    current_params['bandwidth'] = max(1, min(current_params['center_freq'], float(data['bandwidth'])))
    
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
                'message': 'No device selected'
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

if __name__ == '__main__':
    app.run(debug=True)