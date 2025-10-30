import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { motion } from 'framer-motion';
import { GlobalStyles } from './styles/GlobalStyles';
import Header from './components/Header';
import AudioSection from './components/AudioSection';
import ChatSection from './components/ChatSection';
import AnalyticsSection from './components/AnalyticsSection';
import ChartsModal from './components/ChartsModal';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import {
  ControlBar,
  RoomAudioRenderer,
  RoomContext,
} from '@livekit/components-react';
import { Room } from 'livekit-client';
import '@livekit/components-styles';

const serverUrl = 'wss://corelance-1egb2q0f.livekit.cloud';

const LoadingContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-size: 18px;
  color: var(--text-primary);
`;

const MainContainer = styled.main`
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  padding: 0;
  margin: 0;
  overflow: hidden;
`;
const SectionsWrapper = styled.div`
  display: grid;
  grid-template-columns: 1.5fr 1.5fr 1fr; /* Audio bigger, Chat smaller, Analytics compact */
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  width: 100%;
  box-sizing: border-box;
  height: 85vh; /* 🔥 ADD THIS - Fixed height */

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
    gap: var(--spacing-6);
    height: auto;
  }
`;

const AudioSectionWrapper = styled.div`
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--spacing-4);
  box-shadow: var(--shadow-md);
  height: 100%; /* 🔥 CHANGE from min-height to height */
  display: flex;
  flex-direction: column;
  justify-content: space-between;
`;

// 💬 CHAT SECTION — Middle (scrollable + custom scrollbar)
const ChatSectionWrapper = styled.div`
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  height: 100%; /* 🔥 CHANGE from flex: 2 to height: 100% */
  overflow: hidden; /* 🔥 KEEP THIS */
`;


const AnalyticsSectionWrapper = styled.div`
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--spacing-3);
  box-shadow: var(--shadow-md);
  min-height: 85vh;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
`;

const HiddenLiveKitContainer = styled.div`
  position: fixed;
  top: -9999px;
  left: -9999px;
  opacity: 0;
  pointer-events: none;
`;

const ConnectionStatus = styled.div`
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: var(--spacing-2) var(--spacing-4);
  background: ${props => props.connected ? 'var(--success-color)' : 'var(--danger-color)'};
  color: white;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  z-index: 1000;
  box-shadow: var(--shadow-lg);
`;

const AgentStatus = styled.div`
  position: fixed;
  bottom: 60px;
  right: 20px;
  padding: var(--spacing-2) var(--spacing-4);
  background: ${props => props.active ? '#6366f1' : 'var(--bg-tertiary)'};
  color: white;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  z-index: 1000;
  box-shadow: var(--shadow-lg);
`;

function App() {
  const [isChartsModalOpen, setIsChartsModalOpen] = useState(false);
  const [livekitToken, setLivekitToken] = useState(null);
  const [isLoadingToken, setIsLoadingToken] = useState(true);
  const [tokenError, setTokenError] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [agentConnected, setAgentConnected] = useState(false);

  // Room instance
  const [room] = useState(() =>
    new Room({
      adaptiveStream: true,
      dynacast: true,
    })
  );

  // Fetch token once on mount
  useEffect(() => {
    const fetchToken = async () => {
      try {
        const roomName = 'corelance-main-room';
        let identity = sessionStorage.getItem('livekit_identity');
        if (!identity) {
          identity = 'user-' + Math.random().toString(36).substring(7);
          sessionStorage.setItem('livekit_identity', identity);
        }
        
        console.log(`🔑 Requesting token for room: ${roomName}, identity: ${identity}`);
        
        const response = await fetch('http://localhost:5000/api/livekit-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            identity: identity,
            room: roomName
          }),
        });
        
        if (!response.ok) throw new Error('Failed to fetch token from server');
        const data = await response.json();
        setLivekitToken(data.token);
        console.log('✅ LiveKit token fetched successfully for', identity);
      } catch (error) {
        console.error('❌ Failed to fetch LiveKit token:', error);
        setTokenError(error.message);
      } finally {
        setIsLoadingToken(false);
      }
    };
    
    fetchToken();
  }, []);

  // Connect to room when token is available
  useEffect(() => {
    let mounted = true;
    
    const connect = async () => {
      if (!mounted || !livekitToken) return;

      try {
        console.log('🔌 Connecting to LiveKit room...');
        await room.connect(serverUrl, livekitToken);
        console.log('✅ Connected to LiveKit room successfully');
        console.log('Room name:', room.name);
        console.log('Local participant:', room.localParticipant.identity);
        setIsConnected(true);
        
        // Connection state monitoring
        room.on('connectionStateChanged', (state) => {
          console.log('🔄 Connection state changed:', state);
          setIsConnected(state === 'connected');
        });
        
        // CRITICAL: Listen for agent joining
        room.on('participantConnected', (participant) => {
          console.log(`👤 ===== PARTICIPANT CONNECTED =====`);
          console.log(`   Identity: ${participant.identity}`);
          console.log(`   SID: ${participant.sid}`);
          
          // Check if this is the agent
          if (participant.identity.includes('agent') || participant.identity.includes('AI')) {
            console.log('🤖 AI AGENT DETECTED!');
            setAgentConnected(true);
            toast.success('AI Agent connected!', { autoClose: 2000 });
          }
          
          // Subscribe to all tracks
          participant.trackPublications.forEach((publication) => {
            console.log(`   📢 Track: ${publication.kind} (${publication.source})`);
            if (publication.kind === 'audio') {
              publication.setSubscribed(true);
              console.log(`   🔊 Subscribed to audio`);
            }
          });
          
          // Listen for new tracks from this participant
          participant.on('trackPublished', (publication) => {
            console.log(`📢 NEW track published by ${participant.identity}: ${publication.kind}`);
            if (publication.kind === 'audio') {
              publication.setSubscribed(true);
              console.log(`🔊 Subscribed to NEW audio from ${participant.identity}`);
            }
          });
          
          // Track subscribed event
          participant.on('trackSubscribed', (track, publication) => {
            console.log(`✅ Track subscribed: ${track.kind} from ${participant.identity}`);
            if (track.kind === 'audio') {
              console.log(`🔊 AUDIO TRACK ACTIVE from ${participant.identity}`);
            }
          });
        });
        
        // Handle participant disconnect
        room.on('participantDisconnected', (participant) => {
          console.log(`👋 Participant disconnected: ${participant.identity}`);
          if (participant.identity.includes('agent') || participant.identity.includes('AI')) {
            setAgentConnected(false);
            toast.warning('AI Agent disconnected', { autoClose: 2000 });
          }
        });
        
        // Check existing participants
        console.log(`👥 Existing participants: ${room.remoteParticipants.size}`);
        room.remoteParticipants.forEach((participant) => {
          console.log(`   - ${participant.identity}`);
          if (participant.identity.includes('agent') || participant.identity.includes('AI')) {
            setAgentConnected(true);
          }
        });
        
        // Global track subscribed event
        room.on('trackSubscribed', (track, publication, participant) => {
          console.log(`✅ ===== TRACK SUBSCRIBED =====`);
          console.log(`   Kind: ${track.kind}`);
          console.log(`   From: ${participant.identity}`);
          if (track.kind === 'audio') {
            console.log(`🔊 AUDIO IS NOW ACTIVE from ${participant.identity}!`);
          }
        });
        
        // Local track published
        room.localParticipant.on('localTrackPublished', (publication) => {
          console.log(`📤 Local track published: ${publication.kind}`);
        });
        
      } catch (error) {
        console.error('❌ Failed to connect to LiveKit:', error);
        setTokenError('Failed to connect to LiveKit room');
        setIsConnected(false);
      }
    };
    
    connect();
    
    return () => {
      mounted = false;
      if (room.state === 'connected') {
        room.disconnect();
        console.log('🔌 Disconnected from LiveKit room');
      }
      setIsConnected(false);
      setAgentConnected(false);
    };
  }, [room, livekitToken]);

  const openChartsModal = () => setIsChartsModalOpen(true);
  const closeChartsModal = () => setIsChartsModalOpen(false);

  if (isLoadingToken) {
    return (
      <>
        <GlobalStyles />
        <LoadingContainer>
          <div>Loading LiveKit connection...</div>
        </LoadingContainer>
      </>
    );
  }

  return (
    <>
      <GlobalStyles />
      <div className="app">
        <Header />
        <MainContainer>
          <RoomContext.Provider value={room}>
            {/* CRITICAL: RoomAudioRenderer must be visible for audio playback */}
            <HiddenLiveKitContainer data-lk-theme="default">
              <RoomAudioRenderer />
              <ControlBar />
            </HiddenLiveKitContainer>

            {/* Visible UI Components */}
            <SectionsWrapper>
              <AudioSectionWrapper>
                <AudioSection />
              </AudioSectionWrapper>
              
              <ChatSectionWrapper>
                <ChatSection />
              </ChatSectionWrapper>
              
              <AnalyticsSectionWrapper>
                <AnalyticsSection onOpenCharts={openChartsModal} />
              </AnalyticsSectionWrapper>
            </SectionsWrapper>

            {/* Status Indicators */}
            <ConnectionStatus connected={isConnected}>
              {isConnected ? '● Connected to Room' : '● Disconnected'}
            </ConnectionStatus>
            
            <AgentStatus active={agentConnected}>
              {agentConnected ? '🤖 AI Agent Active' : '⏳ Waiting for Agent'}
            </AgentStatus>
          </RoomContext.Provider>
        </MainContainer>
        
        <ChartsModal isOpen={isChartsModalOpen} onClose={closeChartsModal} />
        <ToastContainer />
        
        {tokenError && (
          <div style={{
            position: 'fixed',
            top: '80px',
            right: '20px',
            background: 'var(--danger-color)',
            color: 'white',
            padding: '12px 20px',
            borderRadius: '8px',
            zIndex: 1000
          }}>
            ⚠️ {tokenError}
          </div>
        )}
      </div>
    </>
  );
}

export default App;