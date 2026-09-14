#!/usr/bin/env python3
"""
NeMo Forced Aligner Workflow - Streamlined for ASS file generation
A streamlined Python script for generating ASS subtitle files using NeMo Forced Aligner.

This script focuses only on:
1. Preparing manifest files for NFA
2. Running the forced alignment process to generate ASS files

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
    
    def __init__(self, work_dir: str = r"", nemo_dir: str = r""):
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
    
    # REMOVED - setup_environment method moved to setup.sh script
    
    # COMMENTED OUT - Video download and processing not needed for ASS generation
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
        """Run the NeMo Forced Alignment process to generate ASS files."""
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
        
        # Default configuration for ASS file generation
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
        self.logger.info(f"Alignment completed. ASS files saved to: {output_dir}")
        
        return output_dir

    def get_ass_files(self, nfa_output_dir: str) -> Dict[str, str]:
        """Return paths to generated ASS files."""
        nfa_output_path = Path(nfa_output_dir)
        
        # Find ASS files
        token_ass_files = list((nfa_output_path / "ass" / "tokens").glob("*.ass"))
        word_ass_files = list((nfa_output_path / "ass" / "words").glob("*.ass"))
        
        ass_files = {}
        if token_ass_files:
            ass_files["tokens"] = str(token_ass_files[0])
        if word_ass_files:
            ass_files["words"] = str(word_ass_files[0])
            
        self.logger.info(f"Generated ASS files: {ass_files}")
        return ass_files
    
    # COMMENTED OUT - Video generation not needed for ASS file focus
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
        audio_file: str,
        text: str,
        pretrained_model: str = "stt_en_fastconformer_hybrid_large_pc"
    ) -> Dict[str, Any]:
        """Run the complete NeMo Forced Alignment workflow to generate ASS files."""
        
        results = {}
        
        try:
            # Use provided audio file
            results["audio_path"] = audio_file
            
            # 1. Create manifest
            manifest_path = self.create_manifest(audio_file, text)
            results["manifest_path"] = manifest_path
            
            # 2. Run forced alignment to generate ASS files
            nfa_output_dir = self.run_forced_alignment(manifest_path, pretrained_model)
            results["nfa_output_dir"] = nfa_output_dir
            
            # 3. Get ASS file paths
            ass_files = self.get_ass_files(nfa_output_dir)
            results["ass_files"] = ass_files
            
            # COMMENTED OUT - Video generation not needed for ASS focus
            # subtitled_audios = self.generate_subtitled_audios(audio_path, nfa_output_dir)
            # results["subtitled_audios"] = subtitled_audios
            
            return results
            
        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="NeMo Forced Aligner Workflow - ASS Generation")
    parser.add_argument("--work-dir", default=r"", help="Working directory for output files")
    parser.add_argument("--nemo-dir", default=r"", help="NeMo repository directory")
    # Hardcoded file paths - no need to specify on command line
    # parser.add_argument("--audio-file", required=True, help="Path to audio file for alignment")
    # parser.add_argument("--text", help="Reference text for alignment")
    # parser.add_argument("--text-file", help="File containing reference text")
    parser.add_argument("--model", default="stt_en_fastconformer_hybrid_large_pc", help="Pretrained model name")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    # REMOVED - setup arguments no longer needed (moved to setup.sh)
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Hardcoded file paths
    audio_file = r""
    text_file = r""
    
    # Read text from the hardcoded file
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: Text file not found: {text_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading text file: {e}")
        sys.exit(1)
    
    # Check if audio file exists
    if not os.path.exists(audio_file):
        print(f"Error: Audio file not found: {audio_file}")
        sys.exit(1)
    
    # Initialize workflow
    workflow = NeMoForcedAlignerWorkflow(args.work_dir, args.nemo_dir)
    
    # Run the complete workflow
    try:
        results = workflow.run_complete_workflow(
            audio_file=audio_file,
            text=text,
            pretrained_model=args.model
        )
        
        print("\n" + "="*50)
        print("ASS FILE GENERATION COMPLETED SUCCESSFULLY!")
        print("="*50)
        print(f"Work directory: {workflow.work_dir}")
        print(f"Audio file: {audio_file}")
        print(f"Text file: {text_file}")
        print(f"NFA output directory: {results['nfa_output_dir']}")
        if results.get('ass_files'):
            print("Generated ASS files:")
            for level, path in results['ass_files'].items():
                print(f"  {level}: {path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()