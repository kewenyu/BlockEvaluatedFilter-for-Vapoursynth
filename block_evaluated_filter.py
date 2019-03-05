from functools import partial, reduce
import vapoursynth as vs


class Block:
    """
    This class represent the collection of all blocks which divide the video clip.
    """
    class_name = 'Block'

    @classmethod
    def clip_to_block(cls, clip, blksize):
        """
        This class method convert a video clip into block object.
        :param clip: a gray clip
        :param blksize: size of the block
        :return: a block object
        """
        core = vs.get_core()

        if clip.format.color_family != vs.GRAY:
            raise ValueError(cls.class_name + 'clip must be a gray clip')

        w = clip.width
        h = clip.height
        pad_right = blksize - w % blksize
        pad_bottom = blksize - h % blksize

        clip_padded = clip if pad_right == 0 else core.std.AddBorders(clip, right=pad_right)
        clip_padded = clip_padded if pad_bottom == 0 else core.std.AddBorders(clip_padded, bottom=pad_bottom)
        w += pad_right
        h += pad_bottom

        def cut_row(src):
            row = []
            top = 0
            bottom = h - blksize
            while top <= h and bottom >= 0:
                row.append(core.std.CropRel(src, top=top, bottom=bottom))
                top += blksize
                bottom -= blksize
            return row

        def cut_column(row):
            column = []
            left = 0
            right = w - blksize
            while left <= w and right >= 0:
                column.append(core.std.CropRel(row, left=left, right=right))
                left += blksize
                right -= blksize
            return column

        rows = cut_row(clip_padded)
        blocks = [cut_column(row) for row in rows]

        return cls(blocks, blksize, pad_right, pad_bottom)

    def __init__(self, raw_blocks, blkszie, pad_right=0, pad_bottom=0):
        self._blocks = raw_blocks
        self._blksize = blkszie
        self._pad_right = pad_right
        self._pad_bottom = pad_bottom

    def set_padding(self, padding):
        if not isinstance(padding, (tuple, list)):
            raise ValueError(self.class_name + ': padding must be a tuple or list')
        self._pad_right, self._pad_bottom = padding

    def get_padding(self):
        return self._pad_right, self._pad_bottom

    def get_raw_blocks(self):
        return self._blocks

    def get_block_size(self):
        return self._blksize

    def filter(self, func):
        """
        Apply the given function to all blocks. It's similar to python's built-in filter.
        :param func: a function which accept only one parameter
        :return: none
        """
        self._blocks = [[func(block) for block in row] for row in self._blocks]

    def block_to_clip(self, deblock=False):
        """
        Convert the block object back to a video clip
        :param deblock: whether apply the deblock process to prevent blocking caused by block based process
        :return: a video clip
        """
        core = vs.get_core()

        rows = [reduce(lambda x, y: core.std.StackHorizontal([x, y]), row) for row in self._blocks]
        clip = reduce(lambda x, y: core.std.StackVertical([x, y]), rows)

        if deblock is True:
            import numpy as np

            def draw_mask(n, f):
                fout = f.copy()
                array = np.asarray(f.get_read_array(0))
                for i, x in enumerate(array):
                    for j, y in enumerate(x):
                        if i % self._blksize == 0 or j % self._blksize == 0:
                            array[i, j] = 255
                output_array = np.asarray(fout.get_write_array(0))
                np.copyto(output_array, array)
                return fout

            def minblur(src):
                blur1 = core.rgvs.RemoveGrain(src, 11)
                blur2 = core.rgvs.RemoveGrain(src, 4)
                expr = 'x y - x z - * 0 < x x y - abs x z - abs < y z ? ?'
                return core.std.Expr([src, blur1, blur2], expr)

            blank = core.std.BlankClip(clip, length=1)
            deblock_mask = core.std.ModifyFrame(blank, blank, draw_mask)
            deblock_mask = deblock_mask * clip.num_frames

            blur_clip = minblur(clip)
            deblocked = core.std.MaskedMerge(clip, blur_clip, deblock_mask)
        else:
            deblocked = clip

        final = core.std.CropRel(deblocked, right=self._pad_right, bottom=self._pad_bottom)

        return final


def clip_to_block(clip, blksize):
    """
    An alias for Block.clip_to_block.
    :param clip: Same as Block.clip_to_block
    :param blksize: Same as Block.clip_to_block
    :return: Same as Block.clip_to_block
    """
    return Block.clip_to_block(clip, blksize)


def block_to_clip(blocks, deblock=False):
    """
    An alias for Block.block_to_clip
    :param blocks: a block object
    :param deblock: whether apply a deblock process to prevent blocking
    :return: a video clip
    """
    if not isinstance(blocks, Block):
        raise ValueError("blocks should be a Block object")
    return blocks.block_to_clip(deblock=deblock)


class Filter:
    """
    This class is a collection of some useful block based processing functions.

    Basically there are two type of function: 'xxxx_filter' and 'xxxx_adjust'.

    Functions similar to 'xxxxx_filter' accept a src clip and a filtered clip. Then it decides how much should the
    filtered clip be kept according to certain properties of the block.

    Functions similar to 'xxxxx_adjust' accept a clip and processing function. The processing function should accpet
    a clip and a parameters. The the function will dynamically adjust the parameter of the processing function according
    to certain properties of the block.
    """

    @staticmethod
    def luma_eval_filter(clip, filtered_clip, block_size=128, luma_weight=1.0, offset=0.0, deblock=False, debug=False):
        core = vs.get_core()

        clip_blocks = clip_to_block(clip, block_size)
        padding = clip_blocks.get_padding()

        clip_blocks = clip_blocks.get_raw_blocks()
        filtered_clip_blocks = clip_to_block(filtered_clip, block_size).get_raw_blocks()
        filtered_clip_blocks = [[core.std.PlaneStats(clip, prop='prop') for clip in row] for row in
                                filtered_clip_blocks]

        def process_clip(clip, filtered):
            def process(clip, filtered, n, f):
                luma = f[0].props.propAverage
                weight = max(min(luma * luma_weight + offset, 1), 0)
                final = core.std.Merge(clip, filtered, weight)

                if debug is True:
                    final = core.text.Text(final, str(weight), 5)

                return final

            return core.std.FrameEval(clip, partial(process, clip=clip, filtered=filtered), prop_src=filtered)

        final_blocks = [[process_clip(clip, filtered) for clip, filtered in zip(clip_row, filtered_row)] for
                        clip_row, filtered_row in zip(clip_blocks, filtered_clip_blocks)]
        final_blocks = Block(final_blocks, block_size)
        final_blocks.set_padding(padding)

        return block_to_clip(final_blocks, deblock=deblock)

    @staticmethod
    def luma_complexity_eval_filter(clip, filtered_clip, block_size=128, sigma=1.0, luma_weight=0.2,
                                    complexity_weight=0.8, offset=0.0, deblock=False, debug=False):
        core = vs.get_core()

        mask = core.tcanny.TCanny(filtered_clip, mode=1, op=2, sigma=sigma)
        mask = core.std.Maximum(mask)

        clip_blocks = clip_to_block(clip, block_size)
        padding = clip_blocks.get_padding()

        clip_blocks = clip_blocks.get_raw_blocks()
        filtered_clip_blocks = clip_to_block(filtered_clip, block_size).get_raw_blocks()
        filtered_clip_blocks = [[core.std.PlaneStats(clip, prop='prop') for clip in row] for row in
                                filtered_clip_blocks]
        mask_blocks = clip_to_block(mask, block_size).get_raw_blocks()
        mask_blocks = [[core.std.PlaneStats(clip, prop='prop') for clip in row] for row in mask_blocks]

        def process_clip(clip, filtered, mask):
            def process(clip, filtered, n, f):
                luma = f[0].props.propAverage
                complexity = f[1].props.propAverage
                weight = max(min(luma * luma_weight + (1 - complexity) * complexity_weight + offset, 1), 0)
                final = core.std.Merge(clip, filtered, weight)

                if debug is True:
                    final = core.text.Text(final, str(weight), 5)

                return final

            return core.std.FrameEval(clip, partial(process, clip=clip, filtered=filtered),
                                      prop_src=[filtered, mask])

        final_blocks = [
            [process_clip(clip, filtered, mask) for clip, filtered, mask in zip(clip_row, filtered_row, mask_row)] for
            clip_row, filtered_row, mask_row in zip(clip_blocks, filtered_clip_blocks, mask_blocks)]
        final_blocks = Block(final_blocks, block_size)
        final_blocks.set_padding(padding)

        return block_to_clip(final_blocks, deblock=deblock)

    @staticmethod
    def luma_eval_adjust(clip, func, block_size=128, luma_weight=1.0, para_min=0, para_max=128, para_is_invert=False,
                         offset=0.0, deblock=False, debug=False):
        core = vs.get_core()

        clip_blocks = clip_to_block(clip, block_size)
        padding = clip_blocks.get_padding()

        clip_blocks = clip_blocks.get_raw_blocks()
        clip_blocks = [[core.std.PlaneStats(clip, prop='prop') for clip in row] for row in clip_blocks]

        def process_clip(clip):
            def process(clip, n, f):
                luma = f[0].props.propAverage
                weight = max(min(luma * luma_weight + offset, 1), 0)
                weight = weight if para_is_invert is False else 1 - weight
                parameter = para_min + weight * (para_max - para_min)

                try:
                    final = func(clip, parameter)
                except vs.Error:
                    final = func(clip, round(parameter))

                if debug is True:
                    final = core.text.Text(final, str(parameter), 5)

                return final

            return core.std.FrameEval(clip, partial(process, clip=clip), prop_src=clip)

        final_blocks = [[process_clip(clip) for clip in clip_rows] for clip_rows in clip_blocks]
        final_blocks = Block(final_blocks, block_size)
        final_blocks.set_padding(padding)

        return block_to_clip(final_blocks, deblock=deblock)

    @staticmethod
    def luma_complexity_eval_adjust(clip, func, block_size=128, sigma=1.0, luma_weight=0.2, complexity_weight=0.8,
                                    para_min=0, para_max=128, para_is_invert=False, offset=0.0, deblock=False,
                                    debug=False):
        core = vs.get_core()
        mask = core.tcanny.TCanny(clip, mode=1, op=2, sigma=sigma)
        mask = core.std.Maximum(mask)

        clip_blocks = clip_to_block(clip, block_size)
        padding = clip_blocks.get_padding()

        clip_blocks = clip_blocks.get_raw_blocks()
        clip_blocks = [[core.std.PlaneStats(clip, prop='prop') for clip in row] for row in clip_blocks]
        mask_blocks = clip_to_block(mask, block_size).get_raw_blocks()
        mask_blocks = [[core.std.PlaneStats(mask, prop='prop') for mask in row] for row in mask_blocks]

        def process_clip(clip, mask):
            def process(clip, n, f):
                luma = f[0].props.propAverage
                complexity = f[1].props.propAverage
                weight = max(min(luma * luma_weight + (1 - complexity) * complexity_weight + offset, 1), 0)
                weight = weight if para_is_invert is False else 1 - weight
                parameter = para_min + weight * (para_max - para_min)

                try:
                    final = func(clip, parameter)
                except vs.Error:
                    final = func(clip, round(parameter))

                if debug is True:
                    final = core.text.Text(final, str(parameter), 5)

                return final

            return core.std.FrameEval(clip, partial(process, clip=clip), prop_src=[clip, mask])

        final_blocks = [[process_clip(clip, mask) for clip, mask in zip(clip_row, mask_row)]
                        for clip_row, mask_row in zip(clip_blocks, mask_blocks)]
        final_blocks = Block(final_blocks, block_size)
        final_blocks.set_padding(padding)

        return block_to_clip(final_blocks, deblock=deblock)
