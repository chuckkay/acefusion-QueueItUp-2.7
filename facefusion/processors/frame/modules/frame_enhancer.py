from typing import Any, List, Dict, Literal
import threading
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

import facefusion.globals
import facefusion.processors.frame.core as frame_processors
from facefusion import wording
from facefusion.core import update_status
from facefusion.face_analyser import clear_face_analyser
from facefusion.typing import Frame, Face, Update_Process, ProcessMode, ModelValue, OptionsWithModel
from facefusion.utilities import conditional_download, resolve_relative_path, is_file, is_download_done, get_device
from facefusion.vision import read_image, read_static_image, write_image
from facefusion.processors.frame import globals as frame_processors_globals, choices as frame_processors_choices

FRAME_PROCESSOR = None
THREAD_SEMAPHORE : threading.Semaphore = threading.Semaphore()
THREAD_LOCK : threading.Lock = threading.Lock()
NAME = 'FACEFUSION.FRAME_PROCESSOR.FRAME_ENHANCER'
MODELS: Dict[str, ModelValue] =\
{
	'RealESRGAN_x2plus':
	{
		'url': 'https://github.com/facefusion/facefusion-assets/releases/download/models/RealESRGAN_x2plus.pth',
		'path': resolve_relative_path('../.assets/models/RealESRGAN_x2plus.pth'),
		'scale': 2

	},
	'RealESRGAN_x4plus':
	{
		'url': 'https://github.com/facefusion/facefusion-assets/releases/download/models/RealESRGAN_x4plus.pth',
		'path': resolve_relative_path('../.assets/models/RealESRGAN_x4plus.pth'),
		'scale': 4
	}
}
OPTIONS : OptionsWithModel =\
{
	'model':
	{
		'value': MODELS[frame_processors_globals.frame_enhancer_model],
		'choices': frame_processors_choices.frame_enhancer_models
	}
}


def get_frame_processor() -> Any:
	global FRAME_PROCESSOR

	with THREAD_LOCK:
		if FRAME_PROCESSOR is None:
			model_path = get_options('model').get('path')
			model_scale = get_options('model').get('scale')
			FRAME_PROCESSOR = RealESRGANer(
				model_path = model_path,
				model = RRDBNet(
					num_in_ch = 3,
					num_out_ch = 3,
					scale = model_scale
				),
				device = get_device(facefusion.globals.execution_providers),
				scale = model_scale
			)
	return FRAME_PROCESSOR


def clear_frame_processor() -> None:
	global FRAME_PROCESSOR

	FRAME_PROCESSOR = None


def get_options(key : Literal[ 'model' ]) -> Any:
	return OPTIONS.get(key).get('value')


def set_options(key : Literal[ 'model' ], value : Any) -> None:
	global OPTIONS

	OPTIONS[key]['value'] = value


def pre_check() -> bool:
	if not facefusion.globals.skip_download:
		download_directory_path = resolve_relative_path('../.assets/models')
		model_url = get_options('model').get('url')
		conditional_download(download_directory_path, [ model_url ])
	return True


def pre_process(mode : ProcessMode) -> bool:
	model_url = get_options('model').get('url')
	model_path = get_options('model').get('path')
	if not facefusion.globals.skip_download and not is_download_done(model_url, model_path):
		update_status(wording.get('model_download_not_done') + wording.get('exclamation_mark'), NAME)
		return False
	elif not is_file(model_path):
		update_status(wording.get('model_file_not_present') + wording.get('exclamation_mark'), NAME)
		return False
	if mode == 'output' and not facefusion.globals.output_path:
		update_status(wording.get('select_file_or_directory_output') + wording.get('exclamation_mark'), NAME)
		return False
	return True


def post_process() -> None:
	clear_frame_processor()
	clear_face_analyser()
	read_static_image.cache_clear()


def enhance_frame(temp_frame : Frame) -> Frame:
	with THREAD_SEMAPHORE:
		temp_frame, _ = get_frame_processor().enhance(temp_frame)
	return temp_frame


def process_frame(source_face : Face, reference_face : Face, temp_frame : Frame) -> Frame:
	return enhance_frame(temp_frame)


def process_frames(source_path : str, temp_frame_paths : List[str], update_progress : Update_Process) -> None:
	for temp_frame_path in temp_frame_paths:
		temp_frame = read_image(temp_frame_path)
		result_frame = process_frame(None, None, temp_frame)
		write_image(temp_frame_path, result_frame)
		update_progress()


def process_image(source_path : str, target_path : str, output_path : str) -> None:
	target_frame = read_static_image(target_path)
	result = process_frame(None, None, target_frame)
	write_image(output_path, result)


def process_video(source_path : str, temp_frame_paths : List[str]) -> None:
	frame_processors.multi_process_frames(None, temp_frame_paths, process_frames)
