
        
// Add this to the loadDevices function in your JavaScript
async function loadDevices() {
    try {
        console.log('Fetching audio devices...');
        const response = await fetch('/get_devices');
        const data = await response.json();
        console.log('Received device data:', data);
        
        const inputSelect = document.getElementById('input-device-select');
        const outputSelect = document.getElementById('output-device-select');
        
        inputSelect.innerHTML = '<option value="">Select Input Device</option>';
        outputSelect.innerHTML = '<option value="">Select Output Device</option>';
        
        if (data.status === 'success' && data.devices) {
            console.log(`Found ${data.devices.length} devices`);
            
            data.devices.forEach(device => {
                console.log('Adding device:', device);
                
                // Add to input devices if it has input channels
                if (device.inputs > 0) {
                    const inputOption = document.createElement('option');
                    inputOption.value = device.id;
                    inputOption.textContent = `${device.name} (${device.inputs} in)`;
                    inputSelect.appendChild(inputOption);
                }
                
                // Add to output devices if it has output channels
                if (device.outputs > 0) {
                    const outputOption = document.createElement('option');
                    outputOption.value = device.id;
                    outputOption.textContent = `${device.name} (${device.outputs} out)`;
                    outputSelect.appendChild(outputOption);
                }
            });
        } else {
            console.error('Error loading devices:', data.message);
            inputSelect.innerHTML += '<option disabled>No devices found</option>';
            outputSelect.innerHTML += '<option disabled>No devices found</option>';
        }
    } catch (error) {
        console.error('Error loading devices:', error);
        const inputSelect = document.getElementById('input-device-select');
        const outputSelect = document.getElementById('output-device-select');
        inputSelect.innerHTML += '<option disabled>Error loading devices</option>';
        outputSelect.innerHTML += '<option disabled>Error loading devices</option>';
    }
}

async function selectDevices() {
    const inputDeviceId = document.getElementById('input-device-select').value;
    const outputDeviceId = document.getElementById('output-device-select').value;
    const bufferSize = document.getElementById('buffer-size').value;
    
    if (!inputDeviceId || !outputDeviceId) return;
    
    try {
        const response = await fetch('/select_devices', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                input_device_id: parseInt(inputDeviceId),
                output_device_id: parseInt(outputDeviceId),
                buffer_size: parseInt(bufferSize)
            })
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            console.log('Devices selected:', data.current_params);
        } else {
            console.error('Error selecting devices:', data.message);
        }
    } catch (error) {
        console.error('Error selecting devices:', error);
    }
}

// Add event listeners
document.addEventListener('DOMContentLoaded', loadDevices);
document.getElementById('input-device-select').addEventListener('change', selectDevices);
document.getElementById('output-device-select').addEventListener('change', selectDevices);
document.getElementById('buffer-size').addEventListener('change', selectDevices);

        // Current parameter values
        let currentParams = {
            bandwidth: 250,
            centerFreq: 700
        };
        
        // Drag state
        let isDragging = null;
        let startAngle = 0;
        
        // Get elements
        const bandwidthKnob = document.getElementById('bandwidth-knob');
        const centerKnob = document.getElementById('center-knob');
        const bandwidthIndicator = document.getElementById('bandwidth-indicator');
        const centerIndicator = document.getElementById('center-indicator');
        const valuesDisplay = document.getElementById('values-display');
        
        function updateKnobRotation(knob, angle) {
            const indicator = knob === 'bandwidth' ? bandwidthIndicator : centerIndicator;
            indicator.setAttribute('transform', `rotate(${angle})`);
        }
        
        function calculateValue(angle, knob) {
            if (knob === 'bandwidth') {
                return Math.round(50 + ((angle + 45) / 90) * (500 - 50));
            } else {
                return Math.round(660 + ((angle + 45) / 90) * (740 - 660));
            }
        }
        
        function handleMouseDown(e, knob) {
            isDragging = knob;
            const rect = e.target.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            startAngle = Math.atan2(e.clientY - centerY, e.clientX - centerX);
        }
        
        function handleMouseMove(e) {
            if (!isDragging) return;
            
            const rect = e.target.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const angle = Math.atan2(e.clientY - centerY, e.clientX - centerX);
            
            let rotation = ((angle - startAngle) * 180 / Math.PI);
            rotation = Math.max(-45, Math.min(45, rotation));
            
            updateKnobRotation(isDragging, rotation);
            
            const value = calculateValue(rotation, isDragging);
            if (isDragging === 'bandwidth') {
                currentParams.bandwidth = value;
            } else {
                currentParams.centerFreq = value;
            }
            
            updateDisplay();
        }
        
        function handleMouseUp() {
            if (isDragging) {
                updateParams();
                isDragging = null;
            }
        }
        
        function updateDisplay() {
            valuesDisplay.textContent = `Bandwidth: ${currentParams.bandwidth}Hz | Center: ${currentParams.centerFreq}Hz`;
        }
        
        async function updateParams() {
            try {
                const response = await fetch('/update_params', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        bandwidth: currentParams.bandwidth,
                        center_freq: currentParams.centerFreq
                    })
                });
                const data = await response.json();
                console.log('Parameters updated:', data);
            } catch (error) {
                console.error('Error updating parameters:', error);
                console.log('Attempting to select devices:', {
        input: inputDeviceId,
        output: outputDeviceId,
        buffer: bufferSize
    });
            }
        }
        
        async function startAudio() {
            try {
                const response = await fetch('/start', { method: 'POST' });
                const data = await response.json();
                console.log(data.message);
            } catch (error) {
                console.error('Error starting audio:', error);
            }
        }
        
        async function stopAudio() {
            try {
                const response = await fetch('/stop', { method: 'POST' });
                const data = await response.json();
                console.log(data.message);
            } catch (error) {
                console.error('Error stopping audio:', error);
            }
        }
        


        // Add event listeners
        bandwidthKnob.addEventListener('mousedown', (e) => handleMouseDown(e, 'bandwidth'));
        centerKnob.addEventListener('mousedown', (e) => handleMouseDown(e, 'center'));
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
  