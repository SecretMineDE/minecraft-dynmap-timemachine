import logging
import time
import io

from tqdm import tqdm

from . import projection
from . import simple_downloader
from PIL import Image
from p_tqdm import p_map


class TimeMachine(object):

    def __init__(self, dm_map):
        self._dm_map = dm_map
        # self.dynmap = dynmap.DynMap(url)

    def capture_tile(self, data):
        try:
            img_data = simple_downloader.download(data["img_url"], True)
        except Exception as e:
            logging.info('Unable to download "%s": %s', data["img_url"], str(e))
            return data

        stream = io.BytesIO(img_data)
        im = Image.open(stream)
        data["im"] = im
        return data

    def capture_single(self, map, t_loc, size, parallel=4):
        from_tile, to_tile = t_loc.make_range(size[0], size[1])
        zoomed_scale = projection.zoomed_scale(t_loc.zoom)

        width, height = (
            abs(to_tile.x - from_tile.x) * 128 / zoomed_scale, abs(to_tile.y - from_tile.y) * 128 / zoomed_scale)
        logging.info('final size in px: [%d, %d]', width, height)
        dest_img = Image.new('RGB', (int(width), int(height)))
        tile_list = []

        logging.info("Preparing downloads")
        for x in range(from_tile.x, to_tile.x, zoomed_scale):
            for y in range(from_tile.y, to_tile.y, zoomed_scale):
                img_rel_path = map.image_url(projection.TileLocation(x, y, t_loc.zoom))
                img_url = self._dm_map.url + img_rel_path
                tile_list.append({
                    'from_tile_x': from_tile.x,
                    'from_tile_y': from_tile.y,
                    'to_tile_x': to_tile.x,
                    'to_tile_y': to_tile.y,
                    'x': x,
                    'y': y,
                    'img_url': img_url,
                    'im': None
                })

        logging.info(f"Downloadng using {parallel} threads...")
        tile_list_processed = p_map(self.capture_tile, tile_list, num_cpus=parallel)
        logging.info("Stiching images...")
        for t in tqdm(tile_list_processed):
            box = (int(abs(t["x"] - t["from_tile_x"]) * 128 / zoomed_scale),
                   int((abs(t["to_tile_y"] - t["y"]) - zoomed_scale) * 128 / zoomed_scale))
            dest_img.paste(t["im"], box)

        return dest_img

    def compare_images(self, image1, image2):
        file1data = list(image1.getdata())
        file2data = list(image2.getdata())

        diff = 0
        for i in range(len(file1data)):
            if file1data[i] != file2data[i]:
                diff += 1

        return float(diff) / len(file1data)
