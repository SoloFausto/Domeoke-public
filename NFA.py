#!/usr/bin/env python3
"""
NeMo Forced Aligner Workflow
A streamlined Python script for generating token and word alignments using NeMo Forced Aligner.

This script converts the NeMo Forced Aligner tutorial into a smooth workflow that:

1. Prepares manifest files for NFA
2. Runs the forced alignment process
3. Generates subtitled audios with highlighting

Usage:
    python nemo_forced_aligner_workflow.py 
"""

import os
import json
import subprocess
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import shutil


class NeMoForcedAlignerWorkflow:
    """Main workflow class for NeMo Forced Alignment process."""
    
    def __init__(self, work_dir: str = "WORK_DIR", nemo_dir: str = "NeMo"):
        self.work_dir = Path(work_dir)
        self.nemo_dir = Path(nemo_dir)
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute a shell command with error handling."""
        self.logger.info(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
            if result.stdout:
                self.logger.debug(result.stdout)
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {e}")
            if e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            raise
    
    def setup_environment(self, branch: str = "main", force_reinstall: bool = False):
        """Setup NeMo environment and dependencies."""
        #Probably unnecessary
        self.logger.info("Setting up NeMo environment...")
        
        # Check if we're in Colab or if NeMo directory doesn't exist
        if force_reinstall or not self.nemo_dir.exists():
            self.logger.info("Cloning NeMo repository...")
            if self.nemo_dir.exists():
                shutil.rmtree(self.nemo_dir)
            
            self.run_command([
                "git", "clone", "-b", branch, 
                "https://github.com/NVIDIA/NeMo", str(self.nemo_dir)
            ])
            
            self.logger.info("Installing NeMo...")
            self.run_command([
                sys.executable, "-m", "pip", "install", 
                f"git+https://github.com/NVIDIA/NeMo.git@{branch}#egg=nemo_toolkit[all]"
            ])
        else:
            self.logger.info(f"Using existing NeMo directory: {self.nemo_dir}")
    
    # def download_and_process_video(self, video_url: str, output_filename: str = "one_small_step"):
    #     """Download video and extract audio for processing."""
    #     self.logger.info("Downloading and processing video...")
        
    #     # Create work directory
    #     self.work_dir.mkdir(exist_ok=True)
        
    #     # Download video
    #     original_video = self.work_dir / "original_video.mov"
    #     self.run_command([
    #         "wget", video_url, "-O", str(original_video)
    #     ])
        
    #     # Scale up video for better subtitle quality
    #     output_video = self.work_dir / f"{output_filename}.mp4"
    #     self.run_command([
    #         "/usr/bin/ffmpeg", "-loglevel", "warning", "-y",
    #         "-i", str(original_video),
    #         "-vf", "scale=-1:480",
    #         str(output_video)
    #     ])
        
    #     # Extract audio
    #     output_audio = self.work_dir / f"{output_filename}.wav"
    #     self.run_command([
    #         "/usr/bin/ffmpeg", "-loglevel", "warning", "-y",
    #         "-i", str(original_video),
    #         str(output_audio)
    #     ])
        
    #     self.logger.info(f"Video saved as: {output_video}")
    #     self.logger.info(f"Audio saved as: {output_audio}")
        
    #     return str(output_video), str(output_audio)
    
    def create_manifest(self, audio_filepath: str, text: str, manifest_filename: str = "manifest.json") -> str:
        """Create manifest file for NFA input."""
        self.logger.info("Creating manifest file...")
        
        manifest_filepath = self.work_dir / manifest_filename
        manifest_data = {
            "audio_filepath": audio_filepath,
            "text": text.strip()
        }
        
        with open(manifest_filepath, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Manifest created: {manifest_filepath}")
        return str(manifest_filepath)
    
    def run_forced_alignment(
        self,
        manifest_filepath: str,
        pretrained_model: str = "stt_en_fastconformer_hybrid_large_pc",
        output_dir: Optional[str] = None,
        additional_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Run the NeMo Forced Alignment process."""
        self.logger.info("Running NeMo Forced Alignment...")
        
        if output_dir is None:
            output_dir = str(self.work_dir / "nfa_output")
        
        # Base command
        cmd = [
            "python", str(self.nemo_dir / "tools" / "nemo_forced_aligner" / "align.py"),
            f"pretrained_name={pretrained_model}",
            f"manifest_filepath={manifest_filepath}",
            f"output_dir={output_dir}",
        ]
        
        # Default configuration
        default_config = {
            "additional_segment_grouping_separator": '[".",":","?","!","..."]',
            "ass_file_config.vertical_alignment": "bottom",
            "ass_file_config.text_already_spoken_rgb": "[66,245,212]",
            "ass_file_config.text_being_spoken_rgb": "[242,222,44]",
            "ass_file_config.text_not_yet_spoken_rgb": "[223,242,239]"
        }
        
        # Merge with additional config if provided
        if additional_config:
            default_config.update(additional_config)
        
        # Add config parameters to command
        for key, value in default_config.items():
            cmd.append(f"{key}={value}")
        
        self.run_command(cmd)
        self.logger.info(f"Alignment completed. Output saved to: {output_dir}")
        
        return output_dir
    
    # def generate_subtitled_videos(
    #     self,
    #     video_filepath: str,
    #     nfa_output_dir: str,
    #     output_prefix: str = "subtitled"
    # ) -> Dict[str, str]:
    #     """Generate videos with token and word-level subtitle highlighting."""
    #     self.logger.info("Generating subtitled videos...")
        
    #     nfa_output_path = Path(nfa_output_dir)
    #     video_name = Path(video_filepath).stem
        
    #     # Find ASS files
    #     token_ass_files = list((nfa_output_path / "ass" / "tokens").glob("*.ass"))
    #     word_ass_files = list((nfa_output_path / "ass" / "words").glob("*.ass"))
        
    #     if not token_ass_files or not word_ass_files:
    #         raise FileNotFoundError("Could not find ASS subtitle files in NFA output")
        
    #     token_ass_file = token_ass_files[0]
    #     word_ass_file = word_ass_files[0]
        
    #     # Generate videos
    #     output_files = {}
        
    #     # Token-level highlighting
    #     token_output = self.work_dir / f"{output_prefix}_tokens_aligned.mp4"
    #     self.run_command([
    #         "/usr/bin/ffmpeg", "-loglevel", "warning", "-y",
    #         "-i", video_filepath,
    #         "-vf", f"ass={token_ass_file}",
    #         str(token_output)
    #     ])
    #     output_files["tokens"] = str(token_output)
        
    #     # Word-level highlighting
    #     word_output = self.work_dir / f"{output_prefix}_words_aligned.mp4"
    #     self.run_command([
    #         "/usr/bin/ffmpeg", "-loglevel", "warning", "-y",
    #         "-i", video_filepath,
    #         "-vf", f"ass={word_ass_file}",
    #         str(word_output)
    #     ])
    #     output_files["words"] = str(word_output)
        
    #     self.logger.info(f"Token-aligned video: {output_files['tokens']}")
    #     self.logger.info(f"Word-aligned video: {output_files['words']}")
        
    #     return output_files
    
    def display_alignment_results(self, nfa_output_dir: str):
        """Display sample alignment results from CTM files."""
        self.logger.info("Displaying alignment results...")
        
        nfa_output_path = Path(nfa_output_dir)
        ctm_files = list((nfa_output_path / "ctm").glob("*/*.ctm"))
        
        if ctm_files:
            ctm_file = ctm_files[0]
            print(f"\nSample CTM output from {ctm_file}:")
            with open(ctm_file, 'r') as f:
                for i, line in enumerate(f):
                    if i < 10:  # Show first 10 lines
                        print(line.strip())
                    else:
                        break
        else:
            self.logger.warning("No CTM files found in output directory")
    
    def run_complete_workflow(
        self,
        text: str = None,
        pretrained_model: str = "stt_en_fastconformer_hybrid_large_pc",
        setup_env: bool = True,
        force_reinstall: bool = False
    ) -> Dict[str, Any]:
        """Run the complete NeMo Forced Alignment workflow."""
        
        # # Default text (Neil Armstrong's moon landing speech)
        # if text is None:
        #     text = """
        #     I'm at the foot of the ladder. The LM footpads are only depressed in the
        #     surface about 1 or 2 inches, although the surface appears to be very, very
        #     fine grained, as you get close to it. It's almost like a powder.
        #     Down there, it's very fine. I'm going to step off the LM now. That's one
        #     small step for man, one giant leap for mankind.
        #     """
        
        results = {}
        
        try:
            # 1. Setup environment
            if setup_env:
                self.setup_environment(force_reinstall=force_reinstall)
            
            # 2. Download and process audio
            audio_path, audio_path = self.download_and_process_audio(audio_url)
            results["audio_path"] = audio_path

            audio_file = "processing/input_audio/calle13.mp3"
            lyrics_file = "processing/base_lyrics/calle13.txt"
            
            # 3. Create manifest
            manifest_path = self.create_manifest(audio_file, text)
            results["manifest_path"] = manifest_path
            
            # 4. Run forced alignment
            nfa_output_dir = self.run_forced_alignment(manifest_path, pretrained_model)
            results["nfa_output_dir"] = nfa_output_dir
            
            # # 5. Generate subtitled videos
            # subtitled_audios = self.generate_subtitled_audios(audio_path, nfa_output_dir)
            # results["subtitled_audios"] = subtitled_audios
            
            return results
            
        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="NeMo Forced Aligner Workflow")
    parser.add_argument("--work-dir", default="WORK_DIR", help="Working directory for output files")
    parser.add_argument("--nemo-dir", default="NeMo", help="NeMo repository directory")
    parser.add_argument("--audio-url", help="URL to download audio from")
    parser.add_argument("--text", help="Reference text for alignment")
    parser.add_argument("--text-file", help="File containing reference text")
    parser.add_argument("--model", default="stt_en_fastconformer_hybrid_large_pc", help="Pretrained model name")
    parser.add_argument("--no-setup", action="store_true", help="Skip environment setup")
    parser.add_argument("--force-reinstall", action="store_true", help="Force reinstall of NeMo")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Read text from file if provided
    text = args.text
    if args.text_file:
        with open(args.text_file, 'r', encoding='utf-8') as f:
            text = f.read()
    
    # Initialize workflow
    workflow = NeMoForcedAlignerWorkflow(args.work_dir, args.nemo_dir)
    
    # Set default audio URL if not provided
    audio_url = args.audio_url or "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.v1092338.mov"
    
    # Run the complete workflow
    try:
        results = workflow.run_complete_workflow(
            audio_url=audio_url,
            text=text,
            pretrained_model=args.model,
            setup_env=not args.no_setup,
            force_reinstall=args.force_reinstall
        )
        
        print("\n" + "="*50)
        print("WORKFLOW COMPLETED SUCCESSFULLY!")
        print("="*50)
        print(f"Work directory: {workflow.work_dir}")
        print(f"Original audio: {results['audio_path']}")
        print(f"Token-aligned audio: {results['subtitled_audios']['tokens']}")
        print(f"Word-aligned audio: {results['subtitled_audios']['words']}")
        print(f"NFA output directory: {results['nfa_output_dir']}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()