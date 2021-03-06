# 8 of 12. FREESTYLE

# based on freestyle_to_gpencil by Folkert de Vries
# https://github.com/folkertdev/freestyle-gpencil-exporter

# a tuple containing all strokes from the current render. should get replaced by freestyle.context at some point
def get_strokes():
    return tuple(map(Operators().get_stroke_from_index, range(Operators().get_strokes_size())))

# get the exact scene dimensions
def render_height(scene):
    return int(scene.render.resolution_y * scene.render.resolution_percentage / 100)

def render_width(scene):
    return int(scene.render.resolution_x * scene.render.resolution_percentage / 100)

def render_dimensions(scene):
    return render_width(scene), render_height(scene)

def render_visible_strokes():
    """Renders the scene, selects visible strokes and returns them as a tuple"""
    if (bpy.context.scene.freestyle_gpencil_export.visible_only == True):
        upred = QuantitativeInvisibilityUP1D(0) # visible lines only
    else:
        upred = TrueUP1D() # all lines
    Operators.select(upred)
    Operators.bidirectional_chain(ChainSilhouetteIterator(), NotUP1D(upred))
    Operators.create(TrueUP1D(), [])
    return get_strokes()

def render_external_contour():
    """Renders the scene, selects visible strokes of the Contour nature and returns them as a tuple"""
    upred = AndUP1D(QuantitativeInvisibilityUP1D(0), ContourUP1D())
    Operators.select(upred)
    # chain when the same shape and visible
    bpred = SameShapeIdBP1D()
    Operators.bidirectional_chain(ChainPredicateIterator(upred, bpred), NotUP1D(upred))
    Operators.create(TrueUP1D(), [])
    return get_strokes()


def create_gpencil_layer(scene, name, color, alpha, fill_color, fill_alpha):
    """Creates a new GPencil layer (if needed) to store the Freestyle result"""
    gp = bpy.data.grease_pencil.get("FreestyleGPencil", False) or bpy.data.grease_pencil.new(name="FreestyleGPencil")
    scene.grease_pencil = gp
    layer = gp.layers.get(name, False)
    if not layer:
        print("making new GPencil layer")
        layer = gp.layers.new(name=name, set_active=True)
    elif scene.freestyle_gpencil_export.use_overwrite:
        # empty the current strokes from the gp layer
        layer.clear()

    # can this be done more neatly? layer.frames.get(..., ...) doesn't seem to work
    frame = frame_from_frame_number(layer, scene.frame_current) or layer.frames.new(scene.frame_current)
    return layer, frame 

def frame_from_frame_number(layer, current_frame):
    """Get a reference to the current frame if it exists, else False"""
    return next((frame for frame in layer.frames if frame.frame_number == current_frame), False)

def freestyle_to_gpencil_strokes(strokes, frame, pressure=1, draw_mode="3DSPACE", blenderRender=False):
    scene = bpy.context.scene
    if (scene.freestyle_gpencil_export.doClearPalette == True):
        clearPalette()
    """Actually creates the GPencil structure from a collection of strokes"""
    mat = scene.camera.matrix_local.copy()
    #~ 
    obj = scene.objects.active #bpy.context.edit_object
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me) #from_edit_mesh(me)
    #~
    # this speeds things up considerably
    images = getUvImages()
    #~
    uv_layer = bm.loops.layers.uv.active
    #~
    strokeCounter = 0;
    
    firstRun = True
    allPoints = []
    strokesToRemove = []
    allPointsCounter = 1
    lastActiveColor = None

    for fstroke in strokes:
        # *** fstroke contains coordinates of original vertices ***
        sampleVertRaw = (0,0,0)
        sampleVert = (0,0,0)
        #~
        fstrokeCounter = 0
        for svert in fstroke:
            fstrokeCounter += 1
        for i, svert in enumerate(fstroke):
            if (i == int(fstrokeCounter/2)):
                sampleVertRaw = mat * svert.point_3d
                break
        sampleVert = (sampleVertRaw[0], sampleVertRaw[1], sampleVertRaw[2])
        #~
        pixel = (1,0,1)
        lastPixel = getActiveColor().color
        distances = []
        sortedVerts = bm.verts
        for v in bm.verts:
            distances.append(getDistance(obj.matrix_world * v.co, sampleVert))
        sortedVerts.sort(key=dict(zip(sortedVerts, distances)).get)

        targetVert = None
        for v in sortedVerts:
            targetVert = v
            break
        #~
        try:
            uv_first = uv_from_vert_first(uv_layer, targetVert)
            #uv_average = uv_from_vert_average(uv_layer, v)
            #~
            pixelRaw = None
            if (blenderRender == True):
                pixelRaw = getPixelFromUvArray(images[obj.active_material.texture_slots[0].texture.image.name], uv_first[0], uv_first[1])
            else:
                pixelRaw = getPixelFromUvArray(images[obj.active_material.node_tree.nodes["Image Texture"].image.name], uv_first[0], uv_first[1])                
            pixel = (pixelRaw[0], pixelRaw[1], pixelRaw[2])
        except:
            pixel = lastPixel   
        #~ 
        lastActiveColor = createAndMatchColorPalette(pixel, scene.freestyle_gpencil_export.numMaxColors, scene.freestyle_gpencil_export.numColPlaces)
        #~
        if (scene.freestyle_gpencil_export.use_fill):
            lastActiveColor.fill_color = lastActiveColor.color
            lastActiveColor.fill_alpha = 0.9
        gpstroke = frame.strokes.new(lastActiveColor.name)
        gpstroke.draw_mode = "3DSPACE"
        gpstroke.points.add(count=len(fstroke))

        for svert, point in zip(fstroke, gpstroke.points):
            point.co = mat * svert.point_3d
            point.select = True
            point.strength = 1
            point.pressure = pressure

def freestyle_to_fill(scene):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=1)
    layer, frame = create_gpencil_layer(scene, "freestyle fill", **default)
    # render the external contour 
    strokes = render_external_contour()
    freestyle_to_gpencil_strokes(strokes, frame, draw_mode="3DSPACE")#scene.freestyle_gpencil_export.draw_mode)

def freestyle_to_strokes(scene):
    default = dict(color=(0, 0, 0), alpha=1, fill_color=(0, 1, 0), fill_alpha=0)
    layer, frame = create_gpencil_layer(scene, "freestyle stroke", **default)
    # render the normal strokes 
    #strokes = render_visible_strokes()
    strokes = get_strokes()
    freestyle_to_gpencil_strokes(strokes, frame, draw_mode="3DSPACE")#scene.freestyle_gpencil_export.draw_mode)

def export_stroke(scene, _, x):
    # create stroke layer
    freestyle_to_strokes(scene)

def export_fill(scene, layer, lineset):
    # Doesn't work for 3D due to concave edges
    return

    #if not scene.freestyle_gpencil_export.use_freestyle_gpencil_export:
    #    return 

    #if scene.freestyle_gpencil_export.use_fill:
    #    # create the fill layer
    #    freestyle_to_fill(scene)
    #    # delete these strokes
    #    Operators.reset(delete_strokes=True)

# * * * * * * * * * * * * * * * * * * * * * * * * * *
# * * * * * * * * * * * * * * * * * * * * * * * * * *
# * * * * * * * * * * * * * * * * * * * * * * * * * *

