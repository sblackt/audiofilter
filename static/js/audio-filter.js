import React, { useState } from 'react';

const AudioFilter = () => {
  const [bandwidth, setBandwidth] = useState(250);
  const [centerFreq, setCenterFreq] = useState(700);
  const [isDragging, setIsDragging] = useState(null);

  const updateParams = async () => {
    try {
      const response = await fetch('/update_params', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bandwidth,
          center_freq: centerFreq
        })
      });
      if (!response.ok) {
        console.error('Failed to update parameters');
      }
    } catch (error) {
      console.error('Error updating parameters:', error);
    }
  };

  const handleMouseDown = (knob) => {
    setIsDragging(knob);
  };

  const handleMouseUp = () => {
    if (isDragging) {
      updateParams();
      setIsDragging(null);
    }
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    // Calculate angle from center to mouse position
    let angle = Math.atan2(mouseY - centerY, mouseX - centerX) * (180 / Math.PI);
    // Adjust angle to match knob rotation range (-45 to 45 degrees)
    angle = Math.max(-45, Math.min(45, angle));
    
    if (isDragging === 'bandwidth') {
      const newBandwidth = 50 + ((angle + 45) / 90) * (500 - 50);
      setBandwidth(Math.round(newBandwidth));
    } else if (isDragging === 'center') {
      const newCenter = 660 + ((angle + 45) / 90) * (740 - 660);
      setCenterFreq(Math.round(newCenter));
    }
  };

  const bandwidthRotation = -45 + (bandwidth - 50) / (500 - 50) * 90;
  const centerRotation = -45 + (centerFreq - 660) / (740 - 660) * 90;

  return (
    <div className="flex flex-col items-center w-full max-w-2xl mx-auto p-8">
      <h1 className="text-4xl mb-8 font-light tracking-widest text-neutral-300">
        AUDIO FILTER
      </h1>
      
      <svg 
        viewBox="0 0 400 200" 
        className="w-full"
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Background panel */}
        <rect
          x="20" y="20"
          width="360" height="160"
          rx="8"
          fill="#424242"
          className="filter drop-shadow-lg"
        />
        
        {/* Bandwidth Control */}
        <g 
          transform="translate(100,100)"
          onMouseDown={() => handleMouseDown('bandwidth')}
          onMouseMove={handleMouseMove}
          className="cursor-pointer"
        >
          <circle r="30" fill="#2D2D2D" />
          <rect
            x="-2" y="-16"
            width="4" height="16"
            fill="#E8D5C4"
            transform={`rotate(${bandwidthRotation})`}
          />
          
          {/* Tick marks */}
          <g className="text-[10px] fill-neutral-300">
            <text x="-25" y="-35" textAnchor="middle">50Hz</text>
            <text x="0" y="-40" textAnchor="middle">250Hz</text>
            <text x="25" y="-35" textAnchor="middle">500Hz</text>
          </g>
          
          <text
            y="50"
            textAnchor="middle"
            className="text-sm fill-neutral-300 tracking-wider"
          >
            BANDWIDTH
          </text>
        </g>
        
        {/* Center Frequency Control */}
        <g 
          transform="translate(300,100)"
          onMouseDown={() => handleMouseDown('center')}
          onMouseMove={handleMouseMove}
          className="cursor-pointer"
        >
          <circle r="30" fill="#2D2D2D" />
          <rect
            x="-2" y="-16"
            width="4" height="16"
            fill="#E8D5C4"
            transform={`rotate(${centerRotation})`}
          />
          
          {/* Tick marks */}
          <g className="text-[10px] fill-neutral-300">
            <text x="-25" y="-35" textAnchor="middle">660Hz</text>
            <text x="0" y="-40" textAnchor="middle">700Hz</text>
            <text x="25" y="-35" textAnchor="middle">740Hz</text>
          </g>
          
          <text
            y="50"
            textAnchor="middle"
            className="text-sm fill-neutral-300 tracking-wider"
          >
            CENTRE
          </text>
        </g>
        
        {/* Corner screws */}
        <circle cx="30" cy="30" r="4" fill="#1A1A1A" />
        <circle cx="370" cy="30" r="4" fill="#1A1A1A" />
        <circle cx="30" cy="170" r="4" fill="#1A1A1A" />
        <circle cx="370" cy="170" r="4" fill="#1A1A1A" />
      </svg>
      
      <div className="mt-4 text-neutral-300">
        Bandwidth: {bandwidth}Hz | Center: {centerFreq}Hz
      </div>
    </div>
  );
};

export default AudioFilter;