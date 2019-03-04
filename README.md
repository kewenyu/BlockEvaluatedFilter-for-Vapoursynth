# BlockEvaluatedFilter for Vapoursynth
Process your clip base on block

## Description
BlockEvaluatedFilter for Vapoursynth is a script which process your clip base on
block. It will first divide the clip into block, and then evaluate some properties
 (eg. average luma, complexity) of the block. Processing for blocks will be adjusted
 dynamically according to these properties. An optional deblock process can be applied to the final clip to prevent the blocking artifact caused by this filter. This filter is slow, especially when the block size is small, and is unnecessary to use it most of time.

## Supported Format
Gray clip only

## Requirements
* Vapoursynth >= R33
* Numpy (Optinal. Required if deblock is enabled)

## Functions

#### clip_to_block
This function  divide the clip into blocks. it will return a Block object. <br />
<br />
Usage: <br />
```
clip_to_block(clip, block_size)
```
* block_size </br>
Set the size of block. If the clip's width or height can't be divided by the
block_size, it will be padded automatically.

#### block_to_clip
This function is used to piece blocks together to be a clip. It accept a Block
object. <br />
<br />
Usage: <br />
```
block_to_clip(blocks, deblock=False)
```
* deblock </br>
Whether apply a deblock process to the final clip. Unnecessary in most of time. Numpy is required if enabled.

#### Filter
Filter is static class which contains some useful functions for processing. <br />
There are mainly two type of functions in this class: <br />

* xxxxx_filter <br />
This type of functions process clip, and then decide how much should the result
be kept according to certain properties of the block.
* xxxxx_adjust <br />
  This type of functions accept a clip and a processing function. The processing
function should only accept one clip and one parameter. The function will use the
processing function to process the clip that the parameter in the processing
funtion will be adjusted dynamically accrding to certain properties of the block. You can use functools.partial or lambda expression to produce a processing functions.

Currently, the Filter class has these functions: <br />

###### Filter.luma_complexity_eval_filter
The function will first evaluate the average luma and complexity of the block, and
then it will determine how much should the filtered clip be kept according to a
weight calculated by the average luma and complexity. <br />
<br />
Usage: <br />
```
luma_complexity_eval_filter(clip, filtered_clip, block_size=128, sigma=1.0, luma_weight=0.2, complexity_weight=0.8, offset=0.0, debug=False)
```
* clip <br />
Clip to be processed.
* filtered_clip <br />
Filtered clip to be processed.
* block_size <br />
Size of the block.
* sigma <br />
Sigma for Canny mask which will be used to evaluate complexity.
* luma_weight <br />
The weight of average luma in the final weight.
* complexity_weight <br />
The weight of complexity in the final weight.
* offset <br />
The offset which will be added to the final weight. The final weight will be
clamp between 0 to 1.
* debug <br />
Show the final weight of each block on screen.

The final weight will be calculated in this formula: <br />
<i> luma \* luma_weight + (1 - complexity) \* complexity_weight + offset </i>
<br />
The higher weight is, the more filtered clip will be kept.

###### Filter.luma_complexity_eval_adjust
The function will first evaluate the average luma and complexity of the block, and
then use processing function to process the block while the parameter of the processing
function is being adjusted dynamically according a final weight calculated by
average luma and complexity. <br />
<br />
Usage: <br />
```
luma_complexity_eval_adjust(clip, func, block_size=128, sigma=1.0, luma_weight=0.2, complexity_weight=0.8, para_min=0, para_max=128, para_is_invert=False, offset=0.0, debug=False)
```
* clip <br />
Clip to be processed.
* func <br />
The processing function which will be used to process the clip. This function
should only accept one clip and one parameter.
* block_size <br />
Size of the block.
* sigma <br />
Sigma for Canny mask which will be used to evaluate complexity.
* luma_weight <br />
The weight of average luma in the final weight.
* complexity_weight <br />
The weight of complexity in the final weight.
* para_min <br />
The minimum value of the parameter in the processing function
* para_max <br />
The maximum value of the parameter in the processing function
* para_is_invert <br />
If true, the larger weight is, the smaller parameter will be. Vice versa.
* offset <br />
The offset which will be added to the final weight. The final weight will be
clamp between 0 to 1.
* debug <br />
Show the final value of the parameter of each block on screen.

The parameter will be calculated in this formula: <br />
<i> para_min + (para_max - para_min) \* (para_is_invert ? (1 - weight) : weight) </i>
<br />
While the weight will be calculated in this formula: <br />
<i> luma \* luma_weight + (1 - complexity) \* complexity_weight + offset </i>
<br />

## Data Structure

#### Block
An object which represent all blocks of a clip. Beside the blocks data, it also
contains some useful attributes such as block size and padding size. The Block
object should be the smallest element to be processed in your custom functions.
You are not supposed to construct a Block object. It should be constructed by
the 'clip_to_block' function.
<br /><br />
The Block object has the following methods: <br />
* set_padding(padding) <br />
Override the padding set by the constructor. Padding is a list or tuple which
contains padding_horizontal and padding_vertical.
* get_padding() <br />
Get the padding size from the object.
* get_block_size() <br />
Get the block size from the object.
* get_raw_blocks() <br />
Get the raw block data from the object. It's highly recommened to use 'filter'
method of the object instead of getting the raw block data from the object.
The raw blocks data is a 3 dimensional list.
* filter(func) <br />
Apply the func to all of the blocks.

## Example
```
import vapoursynth as vs
import block_evaluated_filter as bef

core = vs.get_core()

src = xxxxxx  # A gray clip

# Perform a noise reduction according to block's average luma and complexity
# And the complexity play a more significant role than the average luma.
nr = core.knlm.KNLMeansCL(src, a=1, d=1, h=2.0)
nr = bef.Filter.luma_complexity_eval_filter(src, nr, luma_weight=0.3, complexity_weight=0.7)

# Perform a debanding by using f3kdb. And the parameter 'y' of the f3kdb will be adjusted
# dynamically between 32 to 96 according to block's average luma and complexity.
db = bef.Filter.luma_complexity_eval_adjust(nr, lambda clip, y: core.f3kdb.Deband(clip, range=15, y=y, grainy=0), luma_weight=0.5, complexity_weight=0.5,
                                            para_min=32, para_max=96)

db.set_output()
```

## TODO
* Make use of bezier curve to obtain a more flexible adjustment.
* Add more functions to Filter class.
