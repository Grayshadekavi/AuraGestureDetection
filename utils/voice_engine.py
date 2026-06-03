import threading
import queue
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackgroundVoiceEngine:
    def __init__(self):
        """
        A thread-safe Text-to-Speech manager that uses a background worker thread
        and a message queue to prevent blocking the main server threads.
        """
        self.speech_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        
        # Start background worker immediately
        self.start()

    def start(self):
        """Starts the background speech worker thread."""
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()
        logger.info("Background TTS Speech thread started successfully.")

    def _speech_worker(self):
        """Background thread worker that initializes and runs the TTS engine."""
        import pyttsx3
        
        # Initialize engine inside the thread for COM safety (especially on Windows)
        try:
            engine = pyttsx3.init()
            # Optimize speed and voice settings
            engine.setProperty('rate', 165)  # Slightly slower for better clarity
            engine.setProperty('volume', 1.0)
            
            # Select a pleasant voice (usually female if available, otherwise default)
            voices = engine.getProperty('voices')
            if len(voices) > 1:
                # Often index 1 is female in Windows, index 0 is male
                engine.setProperty('voice', voices[1].id)
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3 engine: {e}")
            self.running = False
            return

        while self.running:
            try:
                # Wait for speech text from the queue with a timeout
                phrase = self.speech_queue.get(timeout=1.0)
                if phrase is None:
                    # Sentinel received, shutdown worker
                    break
                
                # Speak the phrase safely
                logger.info(f"Background speech speaking: '{phrase}'")
                engine.say(phrase)
                engine.runAndWait()
                
                # Mark task as done
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error speaking phrase in background: {e}")

        try:
            engine.stop()
        except:
            pass
        logger.info("Background TTS Speech thread shut down.")

    def speak(self, phrase):
        """
        Adds a phrase to the speech queue.
        It is non-blocking and safe to call from any thread.
        """
        if not self.running:
            self.start()
            
        if self.running and phrase:
            # Clear previous items from the queue if they haven't spoken yet
            # to make sure the voice updates instantly to the latest gesture
            while not self.speech_queue.empty():
                try:
                    self.speech_queue.get_nowait()
                    self.speech_queue.task_done()
                except queue.Empty:
                    break
                except ValueError:
                    # Occurs if task_done is called more times than items put
                    break
            
            self.speech_queue.put(phrase)

    def shutdown(self):
        """Safely stops the worker thread."""
        if self.running:
            self.running = False
            self.speech_queue.put(None)  # Add sentinel
            if self.worker_thread:
                self.worker_thread.join(timeout=2.0)
            logger.info("Background TTS Speech engine shutdown completed.")
