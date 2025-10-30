import React, { useState, useEffect, useContext } from "react";
import { RoomContext } from "@livekit/components-react";
import styled from "styled-components";
import { motion } from "framer-motion";

const AudioContainer = styled.div`
  background: var(--bg-card);
  padding: var(--spacing-6);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
`;

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const SectionTitle = styled.h2`
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
`;

const StatusBadge = styled.span`
  padding: var(--spacing-2) var(--spacing-3);
  background: ${(props) =>
    props.isRecording ? "rgba(239, 68, 68, 0.1)" : "rgba(107, 114, 128, 0.1)"};
  color: ${(props) =>
    props.isRecording ? "var(--danger-color)" : "var(--text-muted)"};
  border: 1px solid
    ${(props) =>
      props.isRecording
        ? "rgba(239, 68, 68, 0.2)"
        : "rgba(107, 114, 128, 0.2)"};
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  font-weight: 500;
`;

const AudioVisualization = styled.div`
  height: 120px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-4);
  position: relative;
  overflow: hidden;
`;

const AudioControls = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-4);
`;

const ControlButton = styled(motion.button)`
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: ${(props) => {
    if (props.variant === "record")
      return props.isActive ? "var(--danger-color)" : "rgba(239, 68, 68, 0.1)";
    if (props.variant === "primary") return "var(--primary-color)";
    return "var(--bg-tertiary)";
  }};
  color: ${(props) => {
    if (props.variant === "record")
      return props.isActive ? "white" : "var(--danger-color)";
    if (props.variant === "primary") return "white";
    return "var(--text-secondary)";
  }};
  border: 1px solid
    ${(props) => {
      if (props.variant === "record")
        return props.isActive
          ? "var(--danger-color)"
          : "rgba(239, 68, 68, 0.2)";
      if (props.variant === "primary") return "var(--primary-color)";
      return "var(--border-color)";
    }};
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    transform: scale(1.05);
    box-shadow: var(--shadow-lg);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const AudioStats = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-4);
`;

const StatItem = styled.div`
  background: var(--bg-primary);
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
`;

const StatLabel = styled.div`
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-bottom: var(--spacing-1);
`;

const StatValue = styled.div`
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
`;

const TranscriptionPanel = styled.div`
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-4);
  min-height: 120px;
`;

const TranscriptionHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-3);
`;

const TranscriptionTitle = styled.h3`
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin: 0;
`;

const TranscriptionText = styled.div`
  color: var(--text-primary);
  line-height: 1.6;
  font-size: var(--font-size-sm);
`;

const ErrorMessage = styled.div`
  color: var(--danger-color);
  font-size: var(--font-size-xs);
  padding: var(--spacing-2);
  background: rgba(239, 68, 68, 0.1);
  border-radius: var(--radius-md);
  margin-top: var(--spacing-2);
`;

const AudioSection = () => {

  
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(null);
  const [roomStatus, setRoomStatus] = useState("checking...");
  
  const room = useContext(RoomContext);

  // Check room connection on mount
  useEffect(() => {
    console.log("🔍 AudioSection mounted, checking room...");
    if (room) {
      console.log("✅ Room context available:", room.state);
      setRoomStatus(room.state);
      
      // Listen for room state changes
      const handleStateChange = () => {
        console.log("🔄 Room state changed:", room.state);
        setRoomStatus(room.state);
      };
      
      room.on('connectionStateChanged', handleStateChange);
      
      return () => {
        room.off('connectionStateChanged', handleStateChange);
      };
    } else {
      console.error("❌ No room context available!");
      setRoomStatus("no room");
      setError("Room not connected. Please refresh the page.");
    }
  }, [room]);

  // Timer for recording duration
  useEffect(() => {
    let interval;
    if (isRecording) {
      interval = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setDuration(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

const toggleRecording = async () => {
  if (!room) {
    setError("Room not available. Please refresh the page.");
    console.error("❌ Room not available");
    return;
  }

  const roomParticipant = room.localParticipant;
  
  if (!roomParticipant) {
    setError("Local participant not available. Please refresh.");
    console.error("❌ Local participant not available");
    return;
  }

  try {
    if (!isRecording) {
      console.log("🎤 ===== ENABLING MICROPHONE =====");
      console.log("Room state:", room.state);
      console.log("Remote participants:", room.remoteParticipants.size);
      
      // Enable microphone
      await roomParticipant.setMicrophoneEnabled(true);
      
      // Wait a moment for track to be published
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Check if microphone is actually enabled
      const micTrack = roomParticipant.getTrackPublication('microphone');
      console.log("Microphone track:", micTrack);
      console.log("Microphone enabled:", roomParticipant.isMicrophoneEnabled);
      
      setIsRecording(true);
      setError(null);
      console.log("✅ Microphone enabled successfully");
    } else {
      console.log("⏸️ ===== DISABLING MICROPHONE =====");
      await roomParticipant.setMicrophoneEnabled(false);
      setIsRecording(false);
      console.log("✅ Microphone disabled");
    }
  } catch (err) {
    console.error("❌ Microphone error:", err);
    setError(`Microphone error: ${err.message}`);
    setIsRecording(false);
  }
};

  return (
    <AudioContainer>
      <SectionHeader>
        <SectionTitle>Voice Assistant</SectionTitle>
        <StatusBadge isRecording={isRecording}>
          {isRecording ? "● Recording" : "Ready"}
        </StatusBadge>
      </SectionHeader>

      <AudioVisualization>
        <span style={{ color: "var(--text-muted)", fontSize: "14px" }}>
          {isRecording ? "🎤 Listening..." : "Click microphone to start"}
        </span>
      </AudioVisualization>

      {error && <ErrorMessage>{error}</ErrorMessage>}

      <AudioControls>
        <ControlButton
          variant="record"
          isActive={isRecording}
          onClick={toggleRecording}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          title={isRecording ? "Stop recording" : "Start recording"}
        >
          {isRecording ? "⏸" : "🎤"}
        </ControlButton>
      </AudioControls>

      <AudioStats>
        <StatItem>
          <StatLabel>Duration</StatLabel>
          <StatValue>{formatDuration(duration)}</StatValue>
        </StatItem>
        <StatItem>
          <StatLabel>Room Status</StatLabel>
          <StatValue style={{ fontSize: '14px' }}>{roomStatus}</StatValue>
        </StatItem>
        <StatItem>
          <StatLabel>Mic Status</StatLabel>
          <StatValue style={{ fontSize: '14px' }}>
            {isRecording ? "Active" : "Idle"}
          </StatValue>
        </StatItem>
      </AudioStats>

      <TranscriptionPanel>
        <TranscriptionHeader>
          <TranscriptionTitle>Live Transcription</TranscriptionTitle>
        </TranscriptionHeader>
        <TranscriptionText>
          {isRecording ? (
            <span style={{ color: "var(--text-muted)" }}>
              Waiting for speech...
            </span>
          ) : (
            <span style={{ color: "var(--text-muted)" }}>
              Start recording to see live transcription
            </span>
          )}
        </TranscriptionText>
      </TranscriptionPanel>
    </AudioContainer>
  );
};

export default AudioSection;