import bpy
import json
import os
import math
from bpy.utils import previews
from bpy.types import AddonPreferences, Panel, Scene, WindowManager
from bpy.props import EnumProperty, BoolProperty, StringProperty, FloatProperty, IntProperty, FloatVectorProperty

preview_collections = {}

def log_message(message):
    print(f"Epic Toolbag Addon: {message}")

def update_world_transparency(self, context):
    if context.scene.world_transparent:
        context.scene.render.film_transparent = True
    else:
        context.scene.render.film_transparent = False

def load_hdri_previews(path):
    global preview_collections
    if "hdri_previews" not in preview_collections:
        pcoll = previews.new()
        preview_collections["hdri_previews"] = pcoll
        preview_collections["hdri_paths"] = {}
    else:
        pcoll = preview_collections["hdri_previews"]

    if not os.path.exists(path):
        print(f"HDRI directory not found: {path}")
        return None

    hdri_files = [f for f in os.listdir(path) if f.endswith('.hdr') or f.endswith('.exr')]
    
    for file in hdri_files:
        if file not in pcoll:
            thumbnail_name = os.path.splitext(file)[0] + '.png'
            thumbnail_path = os.path.join(path, thumbnail_name)
            if os.path.exists(thumbnail_path):
                pcoll.load(file, thumbnail_path, 'IMAGE')
                preview_collections["hdri_paths"][file] = os.path.join(path, file)
                log_message(f"HDRI load: {file}")

def unload_hdri_previews():
    global preview_collections
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

def update_hdri(self, context):
    selected_hdri_name = context.scene.hdri_enum
    print(f"Selected HDRI: {selected_hdri_name}")
    apply_hdri_rotation(context)

def apply_hdri_rotation(context):
    world = context.scene.world
    if world and world.use_nodes:
        nodes = world.node_tree.nodes
        mapping_node = next((node for node in nodes if node.type == 'MAPPING'), None)
        if mapping_node:
            rotation_in_radians = math.radians(context.scene.hdri_rotation_degrees) % (2 * math.pi)
            mapping_node.inputs['Rotation'].default_value[2] = rotation_in_radians
            
def get_hdri_items(self, context):
    pcoll = preview_collections.get("hdri_previews")
    if pcoll:
        return [(name, name, "", pcoll[name].icon_id, index) for index, name in enumerate(pcoll.keys())]
    return []

def update_material_list(self, context):
    obj = context.object
    items = []
    if obj:
        for idx, mat in enumerate(obj.data.materials):
            items.append((str(idx), mat.name, "", idx))
    return items

def update_active_material(self, context):
    obj = context.object
    if obj:
        index = int(self.active_material_index)
        if len(obj.material_slots) > index:
            obj.active_material_index = index
                        
class Preferences(AddonPreferences):
    bl_idname = __package__

    last_active_material: StringProperty(
        name="Last Active Material",
        description="Name of the last active material used in the addon",
        default=""
    )

    def get_last_active_material(self):
        if self.last_active_material:
            return bpy.data.materials.get(self.last_active_material)
        return None

    def set_last_active_material(self, material):
        if material:
            self.last_active_material = material.name
        else:
            self.last_active_material = ""

    def clear_last_active_material(self):
        self.last_active_material = ""
                
def add_properties():
    Scene.custom_enum = EnumProperty(
        name="Shader or Render",
        description="Choose between Shader and Render options",
        items=[
            ('SHADER', "Shader", "Access shader options", 'NODE_MATERIAL', 0),
            ('RENDER', "Render", "Access render options", 'SHADERFX', 1)
        ],
        default='SHADER',
    )
    
    # Material Tools View Mode
    Scene.modifier_view_mode = EnumProperty(
        name="Modifier View Mode",
        description="Switch between different modifier view modes",
        items=[
            ('MATERIAL', "Material", "Material settings view"),
            ('MODIFIERS', "Modifiers", "Modifier list and settings"),
            ('FX', "FX", "Effects and modifiers settings"),
        ],
        default='MATERIAL'
    )

    # Mesh Tools View Mode
    Scene.topology_view_mode = EnumProperty(
        name="Topology View Mode",
        description="Switch between different Topology view modes",
        items=[
            ('RETOPOLOGY', "Auto-Remesh", "Retopology tools and settings"),
            ('UV_MAPPING', "UV Mapping", "UV mapping and unwrapping tools"),
        ],
        default='RETOPOLOGY'
    )
        
    Scene.expand_effects = BoolProperty(
        name="Expand Effects",
        description="Expand or collapse the effects section",
        default=False
    )

    # Cel Shading properties
    Scene.cel_shading_settings = BoolProperty(
        name="Cel Shading Settings",
        description="Show/Hide Cel Shading settings",
        default=False
    )
    Scene.shade_steps = IntProperty(
        name="Shading Steps",
        description="Number of shading steps for cel shading effect",
        default=3,
        min=1,
        max=10
    )

    # Dither FX properties
    Scene.dither_fx_settings = BoolProperty(
        name="Dither FX Settings",
        description="Show/Hide Dither FX settings",
        default=False
    )
    Scene.dither_pattern = EnumProperty(
        name="Dither Pattern",
        description="Type of dither pattern to use",
        items=[
            ('BAYER', "Bayer", "Bayer dithering pattern"),
            ('NOISE', "Noise", "Noise dithering pattern"),
            ('PATTERN', "Pattern", "Custom pattern dithering")
        ],
        default='BAYER'
    )
    Scene.dither_scale = FloatProperty(
        name="Dither Scale",
        description="Scale of the dither pattern",
        default=10.0,
        min=0.1,
        max=100.0
    )

    # HDRI properties
    hdri_path = os.path.join(os.path.dirname(__file__), "Source", "HDRI")
    load_hdri_previews(hdri_path)

    Scene.hdri_enum = EnumProperty(
        name="HDRI",
        description="Select an HDRI",
        items=get_hdri_items,
        update=update_hdri
    )

    # Other properties
    WindowManager.active_material_index = EnumProperty(
        name="Active Material",
        description="Select Active Material",
        items=update_material_list,
        update=update_active_material
    )
    
    WindowManager.previous_workspace_name = StringProperty(
        name="Previous Workspace Name",
        description="Stores the name of the previously active workspace",
        default=""
    )

    Scene.expand_column = BoolProperty(
        name="Expand Column",
        description="Expand or collapse the column in the UI for additional options",
        default=False
    )

    Scene.expand_render = BoolProperty(
        name="Expand Render Tools",
        description="Expand or collapse the render tools section",
        default=False
    )
    
    Scene.hdri_files = StringProperty(
        name="HDRI File",
        description="Path to the HDRI file",
        default="",
        subtype='FILE_PATH'
    )

    Scene.world_transparent = BoolProperty(
        name="Transparent World",
        description="Make the world background transparent",
        default=False,
        update=update_world_transparency
    )

    Scene.hdri_rotation_degrees = FloatProperty(
        name="HDRI Rotation (Degrees)",
        description="Rotate the HDRI environment in degrees",
        default=0.0,
        min=0.0,
        max=360.0,
        update=lambda self, context: apply_hdri_rotation(context)
    )

    Scene.expand_light_controls = BoolProperty(
        name="Expand Light Controls",
        description="Expand or collapse the light controls section",
        default=False
    )
    
    Scene.outline_color = FloatVectorProperty(
        name="Outline Color",
        subtype='COLOR',
        default=(0.0, 0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
        description="Define the color of the outline material",
        size=4
    )

    Scene.expand_shader_tools = BoolProperty(
        name="Expand Shader Tools",
        description="Expand or collapse the shader tools section",
        default=False
    )

    Scene.expand_topology_tools = BoolProperty(
        name="Expand Topology Tools",
        description="Expand or collapse the topology tools section",
        default=False
    )

    Scene.expand_imports = BoolProperty(
        name="Expand Imports",
        description="Expand or collapse the imports section",
        default=False
    )
    
    Scene.expand_topology_section = BoolProperty(
    name="Expand Topology Section",
    description="Expand additional topology options",
    default=False
)
    
    Scene.expand_camera = BoolProperty(
        name="Expand Camera",
        description="Expand or collapse the camera section",
        default=False
    )
    
    Scene.expand_set_controls = BoolProperty(
        name="Expand Set Controls",
        description="Expand or collapse the Set Controls section",
        default=False
    )

    Scene.expand_render_tools = BoolProperty(
        name="Expand Render Tools",
        description="Expand or collapse the Render Tools section",
        default=False
    )
          
class EpicToolBagAddonPanel(Panel):
    bl_label = "Epic Toolbag"
    bl_idname = "EPICTOOLBAG_PT_Addon_Panel" 
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Epic Toolbag"

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.scale_y = 2
        row.prop(scene, "custom_enum", expand=True)

        if scene.custom_enum == 'SHADER':
            self.draw_shader_tab(layout, context)
            self.draw_misc_panel(layout, context)
            self.draw_imports_tab(layout, context, scene)

        elif scene.custom_enum == 'RENDER':
            self.draw_render_tab(layout, context)

    def draw_effect_row(self, col, context, effect_type, effect_group):
        scene = context.scene
        obj = context.active_object

        row = col.row(align=True)
        row.scale_y = 1.5
        effect_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES' and 
                        mod.node_group and mod.node_group.name == effect_group), None)
        if not effect_mod:
            row.operator(f"epictoolbag.apply_{effect_type.lower()}_fx", icon='TEXTURE', text=f"{effect_type} FX")
        else:
            row = col.row(align=True)
            row.operator("epictoolbag.remove_shader_effect", icon='X', text="").effect_type = effect_type
            row.prop(scene, f"{effect_type.lower()}_fx_settings", icon='NODE_TEXTURE', text="")
        
        if effect_mod and getattr(scene, f"{effect_type.lower()}_fx_settings"):
            box = col.box()
            self.draw_effect_settings(box, scene, effect_type)

    def draw_effect_settings(self, box, scene, effect_type):
        if effect_type == 'CEL':
            box.prop(scene, "shade_steps", text="Shading Steps")
        elif effect_type == 'DITHER':
            box.prop(scene, "dither_pattern", text="Dither Pattern")
            box.prop(scene, "dither_scale", text="Dither Scale")
        
    @staticmethod
    def validate_context(context):
        obj = context.object
        return obj is not None and obj.type == 'MESH' and obj.active_material is not None

    def draw_shader_tab(self, layout, context):
        obj = context.object

        if obj and obj.type == 'MESH':
            if not EpicToolBagAddonPanel.validate_context(context):
                box = layout.box()
                col = box.column(align=True)
                col.label(text="No Materials Selected", icon='INFO')
                col.separator()
                row = box.row()
                row.scale_y = 1.5
                row.template_ID(obj, "active_material", new="material.new")
                return

            mat = obj.active_material
            if mat:
                preview_id = self.get_id_preview_id(mat)
                box = layout.box()
                
                grid = box.grid_flow(columns=2, align=True)
                col_preview = grid.column(align=True)
                row = col_preview.row()
                row.template_icon(icon_value=preview_id, scale=7.5)
                
                col_primitives = grid.column(align=True)
                primitive_meshes = [
                    ("epictoolbag.create_primitive_cube", 'MESH_CUBE', "Cube"),
                    ("epictoolbag.create_primitive_uv_sphere", 'MESH_UVSPHERE', "UV Sphere"),
                    ("epictoolbag.create_primitive_cylinder", 'MESH_CYLINDER', "Cylinder"),
                    ("epictoolbag.create_primitive_cone", 'MESH_CONE', "Cone"),
                    ("epictoolbag.create_primitive_torus", 'MESH_TORUS', "Torus"),
                    ("epictoolbag.create_primitive_plane", 'MESH_PLANE', "Plane"),
                    ("epictoolbag.create_text", 'FONT_DATA', "Text")
                ]
                
                for op, icon, _ in primitive_meshes:
                    col_primitives.operator(op, text="", icon=icon)
                
                col = box.column()
                row = col.row(align=True)
                row.prop_search(obj, "active_material", bpy.data, "materials", text="")
                row.operator("epictoolbag.refresh_material_inputs", icon="FILE_REFRESH", text="")

                row = layout.row()
                row.scale_y = 1.5
                row.operator("epictoolbag.toggle_expand_column", icon='DOWNARROW_HLT' if context.scene.expand_column else 'RIGHTARROW', text="Tools")
                                
                if context.scene.expand_column:
                    wm = context.window_manager
                    box = layout.box()
                    
                    col = box.column(align=True)
                    col.scale_y = 1.5
                    
                    row = col.row(align=True)
                    row.scale_y = 1.2
                    row.prop(context.scene, "modifier_view_mode", expand=True)
                    
                    if context.scene.modifier_view_mode == 'MATERIAL':
                        col.separator()
                        col.prop(wm, "active_material_index", text="")
                        
                        if mat and mat.node_tree:
                            for node in mat.node_tree.nodes:
                                self.draw_node_properties(box, node, context.scene.expand_column, mat)
                        
                            self.draw_color_ramp_panel(box, context)
                                                    
                        # Verifica se existe um nó Color Ramp antes de chamar
                        color_ramp_node = next((node for node in mat.node_tree.nodes if node.type == 'VALTORGB'), None)
                        if color_ramp_node:
                                self.draw_color_ramp_panel(box, context)
                                                                               
                    elif context.scene.modifier_view_mode == 'MODIFIERS':
                        col.separator()
                        row = col.row(align=True)
                        row.scale_y = 1.2         
                        # Botão para adicionar modificador com dropdown
                        row.operator("epictoolbag.add_specific_modifier", text="Add Modifier", icon='ADD')   
                        row.operator("epictoolbag.update_geometry_nodes", text="", icon='FILE_REFRESH')
                        
                        if obj.modifiers:
                            for mod in obj.modifiers:
                                self.draw_single_modifier(col, mod, obj, context)
                                        
                    elif context.scene.modifier_view_mode == 'FX':
                        col.separator()
                                                            
                        fx_effects = [
                            ("object.create_outline", "Outline", 'MOD_SOLIDIFY'),
                            ("epictoolbag.apply_cel_shading", "Cel Shader", 'SHADING_RENDERED'),
                            ("epictoolbag.dither_fx", "Dither", 'NODE_TEXTURE') 
                        ]

                        for add_op, label, icon in fx_effects:
                            try:
                                row = col.row(align=True)
                                row.scale_y = 1.2
                                row.operator(add_op, text=label, icon=icon)
                            except Exception as e:
                                print(f"Error drawing FX effect {label}: {e}")

                        # Configurações de Dither
                        try:
                            dither_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES' and 
                                            mod.node_group and mod.node_group.name.lower() == 'dither'), None)
                            
                            print(f"Dither Modifier found: {dither_mod}")  # Log de depuração

                            if dither_mod:
                                row = col.row(align=True)
                                row.operator("epictoolbag.remove_shader_effect", icon='X', text="").effect_type = 'DITHER'
                                row.prop(context.scene, "dither_fx_settings", icon='NODE_TEXTURE', text="")
                                print("Dither settings row added")  # Log de depuração

                            if context.scene.dither_fx_settings:
                                box = col.box()
                                box.prop(context.scene, "dither_pattern", text="Dither Pattern")
                                box.prop(context.scene, "dither_scale", text="Dither Scale")
                                print("Dither settings box added")  # Log de depuração
                        except Exception as e:
                            print(f"Error processing Dither modifier: {e}")

        elif obj and obj.type == 'GPENCIL':
            box = layout.box()
            col = box.column(align=True)
            
            # Mensagem de erro em vermelho centralizada
            warning_row = col.row()
            warning_row.alignment = 'CENTER'
            warning_row.alert = True
            warning_row.label(text="Grease Pencil support is not available.", icon='ERROR')
            
            col.separator()
            
            # Botão de feedback centralizado
            feedback_row = col.row(align=True)
            feedback_row.alignment = 'CENTER'
            feedback_row.operator("wm.url_open", text="Suggest Features", icon='COMMUNITY').url = "https://report-bugs.netlify.app/"
            
        elif obj and obj.type == 'FONT':
            self.draw_text_tools(layout, obj)
        
        else:
            box = layout.box()
            col = box.column(align=True)
            
            # Título principal centralizado
            row = col.row()
            row.alignment = 'CENTER'
            row.label(text="Select Object Material", icon='INFO')
            
            # Mensagem de erro em vermelho
            warning_row = col.row()
            warning_row.alignment = 'CENTER'
            warning_row.alert = True
            warning_row.label(text="No object or material selected.", icon='ERROR')
            
    def draw_single_modifier(self, layout, mod, obj, context):
        # Depuração
        print(f"ALL Modifier Types: {mod.type}")
        print(f"Modifier Name: {mod.name}")
        
        # Verificação especial para modificadores de nós do tipo Outline
        if mod.type == 'NODES' and mod.node_group:
            outline_names = ['Outline', 'Outline Effects', 'OutlineEffect']
            
            # Verifica se o nome do grupo corresponde a um nome de contorno
            if any(name.lower() in mod.node_group.name.lower() for name in outline_names):
                # Cria o box do modificador
                mod_box = layout.box()
                row = mod_box.row(align=True)
                row.scale_y = 1.2
                
                # Botão de expansão
                expand_icon = 'TRIA_RIGHT' if not mod.show_expanded else 'TRIA_DOWN'
                row.prop(mod, "show_expanded", text="", icon=expand_icon, emboss=False)
                
                # Nome do modificador
                row.prop(mod, "name", text="", icon='MOD_SOLIDIFY', emboss=False)
                
                # Botões de visualização
                row.prop(mod, "show_viewport", text="", icon='RESTRICT_VIEW_OFF' if mod.show_viewport else 'RESTRICT_VIEW_ON')
                row.prop(mod, "show_render", text="", icon='RESTRICT_RENDER_OFF' if mod.show_render else 'RESTRICT_RENDER_ON')
                
                # Botão de aplicar modificador
                row.operator("object.modifier_apply", text="", icon='CHECKMARK').modifier = mod.name
                
                # Botão de remover
                row.operator("object.modifier_remove", text="", icon='X').modifier = mod.name
                
                # Botões de mover
                if len(obj.modifiers) > 1:
                    sub = row.row(align=True)
                    sub.scale_x = 0.8
                    sub.operator("object.modifier_move_up", text="", icon='TRIA_UP').modifier = mod.name
                    sub.operator("object.modifier_move_down", text="", icon='TRIA_DOWN').modifier = mod.name
                
                # Tratamentos específicos para cada tipo de modificador
                if mod.show_expanded:
                    col = mod_box.column(align=True)
                    
                    # Tenta encontrar inputs relevantes
                    for node in mod.node_group.nodes:
                        if node.type not in ['GROUP_INPUT', 'GROUP_OUTPUT']:
                            for input in node.inputs:
                                # Condições para mostrar inputs
                                if (not input.is_linked and 
                                    input.name not in ["Outline Color", "Base Color", "Rim Color"] and 
                                    input.type not in ['RGBA', 'COLOR']):
                                    try:
                                        col.prop(input, "default_value", text=input.name)
                                    except Exception as e:
                                        print(f"Error drawing Outline input: {e}")
                
                return  # Encerra o processamento após tratar o modificador Outline
    
        # Cria o box do modificador para tipos padrão
        mod_box = layout.box()
        row = mod_box.row(align=True)
        row.scale_y = 1.2
        
        # Determina o ícone do modificador
        icon = self.get_modifier_icon(mod.type)
        
        # Botão de expansão
        expand_icon = 'TRIA_RIGHT' if not mod.show_expanded else 'TRIA_DOWN'
        row.prop(mod, "show_expanded", text="", icon=expand_icon, emboss=False)
        
        # Nome do modificador
        row.prop(mod, "name", text="", icon=icon, emboss=False)
        
        # Botões de visualização
        row.prop(mod, "show_viewport", text="", icon='RESTRICT_VIEW_OFF' if mod.show_viewport else 'RESTRICT_VIEW_ON')
        row.prop(mod, "show_render", text="", icon='RESTRICT_RENDER_OFF' if mod.show_render else 'RESTRICT_RENDER_ON')
        
        # Botão de aplicar modificador
        row.operator("object.modifier_apply", text="", icon='CHECKMARK').modifier = mod.name
        
        # Botão de remover
        row.operator("object.modifier_remove", text="", icon='X').modifier = mod.name
        
        # Botões de mover
        if len(obj.modifiers) > 1:
            sub = row.row(align=True)
            sub.scale_x = 0.8
            sub.operator("object.modifier_move_up", text="", icon='TRIA_UP').modifier = mod.name
            sub.operator("object.modifier_move_down", text="", icon='TRIA_DOWN').modifier = mod.name
        
        # Tratamentos específicos para cada tipo de modificador
        if mod.show_expanded:
            if mod.type == 'ARRAY':
                col = mod_box.column(align=True)
                col.prop(mod, "fit_type", text="Fit Type")
                col.prop(mod, "count", text="Count")
                col.prop(mod, "relative_offset_displace", text="Offset")
                row = col.row()
                row.prop(mod, "use_merge_vertices", text="Merge")
                row.prop(mod, "merge_threshold", text="Threshold")

            elif mod.type == 'BEVEL':
                col = mod_box.column(align=True)
                col.prop(mod, "segments", text="Segments")
                col.prop(mod, "width", text="Width")
                col.prop(mod, "offset_type", text="Offset")

            elif mod.type == 'BOOLEAN':
                col = mod_box.column(align=True)
                col.prop(mod, "operation", text="Operation")
                col.prop(mod, "object", text="Target")
                col.prop(mod, "solver", text="Solver")
                col.prop(mod, "use_self", text="Self Intersection")

            elif mod.type == 'CURVE':
                col = mod_box.column(align=True)
                col.prop(mod, "deform_axis", text="Deform Axis")
                col.prop(mod, "object", text="Curve")

            elif mod.type == 'DECIMATE':
                col = mod_box.column(align=True)
                col.prop(mod, "face_count", text="Face Count")
                col.prop(mod, "mode", text="Mode")
                col.prop(mod, "ratio", text="Ratio")
                row = col.row()
                row.prop(mod, "use_symmetry_x", text="X")
                row.prop(mod, "use_symmetry_y", text="Y")
                row.prop(mod, "use_symmetry_z", text="Z")
                col.prop(mod, "triangulate", text="Triangulate")

            elif mod.type == 'MIRROR':
                col = mod_box.column(align=True)
                row = col.row()
                row.prop(mod, "use_x", text="X")
                row.prop(mod, "use_y", text="Y")
                row.prop(mod, "use_z", text="Z")
                col.prop(mod, "mirror_object", text="Mirror Object")
                col.prop(mod, "merge_threshold", text="Merge Threshold")

            elif mod.type == 'MULTIRES':
                col = mod_box.column(align=True)
                col.prop(mod, "levels", text="Levels")
                col.prop(mod, "render_levels", text="Render Levels")
                row = col.row()
                row.operator("object.multires_subdivide", text="Subdivide")

            elif mod.type == 'SMOOTH':
                col = mod_box.column(align=True)
                col.prop(mod, "factor", text="Factor")
                col.prop(mod, "iterations", text="Iterations")
                row = col.row()
                row.prop(mod, "use_x", text="X")
                row.prop(mod, "use_y", text="Y")
                row.prop(mod, "use_z", text="Z")

            elif mod.type == 'SUBSURF':
                col = mod_box.column(align=True)
                col.prop(mod, "levels", text="Levels")
                col.prop(mod, "render_levels", text="Render Levels")
            
            elif mod.type == 'SOLIDIFY':
                col = mod_box.column(align=True)
                col.prop(mod, "thickness", text="Thickness")
                col.prop(mod, "offset", text="Offset")
                row = col.row()
                row.prop(mod, "use_even_offset", text="Even Thickness")
                row.prop(mod, "use_quality_normals", text="High Quality")
                col.prop(mod, "thickness_clamp", text="Thickness Clamp")

            elif mod.type == 'SHRINKWRAP':
                col = mod_box.column(align=True)
                col.prop(mod, "target", text="Target")
                col.prop(mod, "wrap_method", text="Wrap Method")
                col.prop(mod, "wrap_mode", text="Wrap Mode")
                col.prop(mod, "offset", text="Offset")
                row = col.row()
                row.prop(mod, "use_project_x", text="X")
                row.prop(mod, "use_project_y", text="Y")
                row.prop(mod, "use_project_z", text="Z")
                            
            elif mod.type == 'OUTLINE':
                col = mod_box.column(align=True)
                col.label(text="Outline Modifier Controls", icon='MOD_SOLIDIFY')
                
                # Adicione propriedades específicas do Outline aqui
                col.prop(mod, "thickness", text="Thickness")
                   
    def get_modifier_icon(self, mod_type):
        icons = {
            'SUBSURF': 'MOD_SUBSURF',        # Subdivision Surface
            'SMOOTH': 'MOD_SMOOTH',          # Smooth
            'DECIMATE': 'MOD_DECIM',         # Decimate
            'MULTIRES': 'MOD_MULTIRES',      # Multiresolution
            'BEVEL': 'MOD_BEVEL',            # Bevel
            'CURVE': 'MOD_CURVE',            # Curve
            'MIRROR': 'MOD_MIRROR',          # Mirror
            'NODES': 'NODETREE',             # Geometry Nodes
            'BOOLEAN': 'MOD_BOOLEAN',        # Boolean
            'ARRAY': 'MOD_ARRAY',            # Array Modifier
            'SOLIDIFY': 'MOD_SOLIDIFY',      # Solidify
            'SHRINKWRAP': 'MOD_SHRINKWRAP'   # Shrinkwrap
        }
        return icons.get(mod_type, 'MODIFIER')
        
    def draw_text_tools(self, layout, obj):
        text_data = obj.data
        mat = obj.active_material

        # Check if the object is a text object
        if not isinstance(obj.data, bpy.types.TextCurve):
            box_info = layout.box()
            row_info = box_info.row()
            row_info.alignment = 'CENTER'
            row_info.label(text="Select a Text Object", icon='INFO')
            return

        # Text properties
        box = layout.box()
        row = box.row(align=True)
        row.prop(text_data, "font", text="")
        row.operator("font.open", text="", icon='FILE_FOLDER')
        row.prop(text_data, "bold", toggle=True)
        row.prop(text_data, "italic", toggle=True)
        row.prop(text_data, "underline", toggle=True)

        box = layout.box()
        box.prop(text_data, "body", text="Type")
        box.prop(text_data, "align_x", text="Align X")
        box.prop(text_data, "align_y", text="Align Y")
        box.prop(text_data, "size", text="Size")

        # Material properties
        box = layout.box()
        row = box.row(align=True)
        row.scale_y = 1.5
        row.prop_search(obj, "active_material", bpy.data, "materials", text="Material")
        
        if obj.data.materials:
            current_mat = obj.active_material
            if current_mat and current_mat.use_nodes:
                principled_node = current_mat.node_tree.nodes.get("Principled BSDF")
                if principled_node:
                    row.operator("epictoolbag.add_text_material", text="", icon='ADD')

        if mat and mat.use_nodes:
            principled_node = mat.node_tree.nodes.get("Principled BSDF")
            color_ramp_node = next((node for node in mat.node_tree.nodes if node.type == 'VALTORGB'), None)
            
            row = box.row(align=True)
            row.scale_y = 1.5
            
            if principled_node:
                row.prop(principled_node.inputs["Base Color"], "default_value", text="Base Color")
            
            if color_ramp_node:
                self.draw_color_ramp_panel(layout, context)
            
            if not principled_node and not color_ramp_node:
                box_info = box.box()
                row_info = box_info.row()
                row_info.alignment = 'CENTER'
                row_info.label(text="No Usable Color Node", icon='ERROR')

        else:
            box_info = box.box()
            row_info = box_info.row()
            row_info.alignment = 'CENTER'
            row_info.label(text="Select a Material", icon='ERROR')
        
        # New Box for "Add Modifiers" or "Apply Convert to Mesh"
        box_modifiers = layout.box()
        row_modifiers = box_modifiers.row(align=True)
        row_modifiers.scale_y = 1.2

        if isinstance(obj.data, bpy.types.TextCurve):
            row_modifiers.operator("epictoolbag.convert_text_to_mesh", text="Apply Convert to Mesh", icon='MESH_DATA')

        # Display existing modifiers for the text object
        if obj.modifiers:
            for mod in obj.modifiers:
                self.draw_single_modifier(box_modifiers, mod, obj, context)
                
    @staticmethod
    def get_id_preview_id(mat):
        if mat and mat.preview:
            return mat.preview.icon_id
        return 0

    def draw_color_ramp_panel(self, layout, context):
        # Determina o nó Color Ramp
        color_ramp_node = None
        
        # Se for um nó Color Ramp direto
        if hasattr(context, 'type') and context.type == 'VALTORGB':
            color_ramp_node = context
        
        # Se for um contexto de material
        elif hasattr(context, 'object') and context.object and context.object.active_material:
            mat = context.object.active_material
            
            if mat.use_nodes:
                color_ramp_node = next((node for node in mat.node_tree.nodes if node.type == 'VALTORGB'), None)
        
        # Se encontrou um nó Color Ramp, desenha
        if color_ramp_node:
            box = layout.box()
            box.label(text="Color Ramp", icon='COLOR')
            box.template_color_ramp(color_ramp_node, "color_ramp", expand=True)

    def draw_tex_image_node(self, layout, node, expand_column):
        box = layout.box()
        row = box.row(align=True)
        row.scale_y = 1.5 
        row.prop(node, "name", text="Texture Node")
        row.label(icon='NODE_TEXTURE')
        
        if expand_column:
            # Preview da imagem
            if node.image:
                box.template_ID_preview(node, "image", new="image.new", open="image.open", rows=1, cols=1)
            
            # Informações e propriedades da textura
            col = box.column(align=True)
            col.scale_y = 1.5
            
            # Propriedades de mapeamento
            col.prop(node, "projection", text="Projection")
            col.prop(node, "extension", text="Extension")
            col.prop(node, "source", text="Source")
            col.prop(node, "color_space", text="Color Space")
            
    def draw_node_properties(self, layout, node, expand_column, mat=None):
        # Lista de nós a serem ignorados
        ignored_nodes = [
            'Material Output', 
            'Group Input', 
            'Group Output', 
            'Volume', 
            'Displacement', 
            'Thickness'
        ]
        
        # Verifica se o nome do nó está na lista de nós ignorados
        if node.name in ignored_nodes or node.type in {'OUTPUT_MATERIAL', 'GROUP_INPUT', 'GROUP_OUTPUT'}:
            return

        # Verifica se o nó é um nó de Color Ramp
        if node.type == 'VALTORGB':
            self.draw_color_ramp_panel(layout, node)
            return

        # Verifica se o nó é de imagem de textura
        if node.type == 'TEX_IMAGE':
            self.draw_tex_image_node(layout, node, expand_column)
            return

        # Verifica se é um nó Principled BSDF
        if node.type == 'BSDF_PRINCIPLED':
            box = layout.box()
            row = box.row(align=True)
            row.scale_y = 1.5
            row.prop(node, "name", text="Shader")
            row.label(icon='NODE_MATERIAL')

            if expand_column:
                desired_inputs = [
                    'Base Color', 
                    'Metallic', 
                    'Specular', 
                    'Roughness', 
                    'IOR', 
                    'Alpha', 
                    'Emission Color',
                ]
                
                for input in node.inputs:
                    if input.name in desired_inputs:
                        row = box.row()
                        row.scale_y = 1.0
                        icon = 'COLOR' if input.type == 'RGBA' else 'NONE'
                        row.prop(input, "default_value", text=input.name, icon=icon)
            return

        # Para outros tipos de nós
        box = layout.box()
        row = box.row(align=True)
        row.scale_y = 1.5
        row.prop(node, "name", text="")
        row.label(icon='NODE')

        if expand_column:
            for input in node.inputs:
                # Pula inputs de vetor e inputs conectados
                if input.name == 'Vector' or input.is_linked:
                    continue
                
                # Processa inputs de tipos específicos
                if input.type in {'RGBA', 'VALUE', 'VECTOR', 'STRING', 'BOOLEAN'}:
                    row = box.row()
                    row.scale_y = 1.0
                    icon = 'COLOR' if input.type == 'RGBA' else 'NONE'
                    row.prop(input, "default_value", text=input.name, icon=icon)
                else:
                    # Para tipos de input não suportados
                    row = box.row()
                    row.label(text=f"{input.name} ({input.type})", icon='BLANK1')
                                
    def draw_misc_panel(self, layout, context, force_collapse=False):
        scene = context.scene
        obj = context.active_object

        if obj and obj.type == 'MESH':
            row = layout.row()
            row.scale_y = 1.5
            row.operator("epictoolbag.toggle_expand_topology_tools", 
                        icon='DOWNARROW_HLT' if scene.expand_topology_tools else 'RIGHTARROW', 
                        text="Topology")
            
            if scene.expand_topology_tools:
                box = layout.box()
                col = box.column(align=True)
                col.scale_y = 1.5

                row = col.row(align=True)
                row.scale_y = 1.2
                row.prop(scene, "topology_view_mode", expand=True)

                col.separator()

    def draw_misc_panel(self, layout, context, force_collapse=False):
        scene = context.scene
        obj = context.active_object

        if obj and obj.type == 'MESH':
            # Linha para o botão de expansão das ferramentas de topologia
            row = layout.row()
            row.scale_y = 1.5
            row.operator(
                "epictoolbag.toggle_expand_topology_tools",
                icon='DOWNARROW_HLT' if scene.expand_topology_tools else 'RIGHTARROW',
                text="Topology"
            )

            # Verifica se as ferramentas de topologia estão expandidas
            if scene.expand_topology_tools:
                # Caixa principal para as configurações de topologia
                box = layout.box()
                
                # Coluna para o modo de visualização de topologia
                col = box.column(align=True)
                col.scale_y = 1.5
                
                # Linha para o modo de visualização de topologia
                row = col.row(align=True)
                row.scale_y = 1.2
                row.prop(scene, "topology_view_mode", expand=True)
                
                col.separator()
                
                # Configurações específicas para o modo de visualização 'RETOPOLOGY'
                if scene.topology_view_mode == 'RETOPOLOGY':
                    # Caixa para configurações de Remesh
                    remesh_box = col.box()
                    remesh_col = remesh_box.column(align=True)

                    # Abas para seleção do modo de remeshing (Sharp, Smooth, Voxel)
                    row = remesh_col.row(align=True)
                    row.prop(scene.epic_advanced_remesh, "remesh_mode", expand=True)

                    # Controle deslizante para preservação de detalhes
                    row = remesh_col.row(align=True)
                    row.prop(scene.epic_advanced_remesh, "detail_preservation", text="", slider=True)
                    
                    # Symmetry com ícone e caixas alinhadas à direita abaixo da barra de porcentagem
                    symmetry_row = remesh_col.row(align=True)
                    symmetry_row.alignment = 'EXPAND'
                    symmetry_row.label(text="Symmetry", icon='MOD_MIRROR')

                    # Alinhar as caixas XYZ à direita
                    symmetry_boxes = symmetry_row.row(align=True)
                    symmetry_boxes.alignment = 'RIGHT'
                    symmetry_boxes.prop(scene.epic_advanced_remesh, "symmetry_x", text="X")
                    symmetry_boxes.prop(scene.epic_advanced_remesh, "symmetry_y", text="Y")
                    symmetry_boxes.prop(scene.epic_advanced_remesh, "symmetry_z", text="Z")
                    
                    # Botão para executar o Remesh
                    row = remesh_col.row(align=True)
                    row.scale_y = 1.5
                    row.operator("epictoolbag.advanced_remesher", text="Advanced Remesh")
                    
                    # Seção para exibição de métricas de desempenho
                    if scene.epic_advanced_remesh.remesh_performance_metrics:
                        try:
                            metrics = eval(scene.epic_advanced_remesh.remesh_performance_metrics)
                            perf_box = remesh_col.box()
                            perf_col = perf_box.column(align=True)
                            
                            # Redução de complexidade
                            reduction_row = perf_col.row(align=True)
                            reduction_row.alignment = 'LEFT'
                            reduction_row.label(text="Reduction:", icon='MESH_GRID')
                            reduction_row.label(text=f"{metrics['complexity_reduction']:.2f}%")
                            
                            # Tempo de processamento
                            time_row = perf_col.row(align=True)
                            time_row.alignment = 'LEFT'
                            time_row.label(text="Time:", icon='TIME')
                            time_row.label(text=f"{metrics['processing_time']:.4f}s")
                            
                            # Contagem de polígonos original
                            poly_row = perf_col.row(align=True)
                            poly_row.alignment = 'LEFT'
                            poly_row.label(text="Original Count:", icon='MESH_CUBE')
                            poly_row.label(text=str(metrics['original_poly_count']))
                            
                            # Nova contagem de polígonos
                            poly_new_row = perf_col.row(align=True)
                            poly_new_row.alignment = 'LEFT'
                            poly_new_row.label(text="New Count:", icon='MESH_GRID')
                            poly_new_row.label(text=str(metrics['new_poly_count']))
                        
                        except Exception as e:
                            self.report({'ERROR'}, f"Error processing performance metrics: {e}")
                        
                elif scene.topology_view_mode == 'UV_MAPPING':
                    # Box principal de UV Mapping
                    uv_box = col.box()
                    uv_col = uv_box.column(align=True)

                    # Botões de UV Editor
                    row = uv_col.row(align=True)
                    row.scale_y = 1.2
                    row.operator("epictoolbag.preview_uv_editing", text="UV Editor", icon='MESH_GRID')
                    row.operator("epictoolbag.revert_workspace", text="", icon='LOOP_BACK')

                    # Botões de Checker Texture
                    row = uv_col.row(align=True)
                    row.scale_y = 0.8
                    row.operator("epictoolbag.add_checker_texture", text="Add Checker UV", icon='TEXTURE')
                    row.operator("epictoolbag.remove_checker_texture", text="", icon='X')

                    uv_col.separator()

                    # Funções do modo editor
                    if context.object.mode == 'EDIT':
                        # Seleção: Vertex | Edge | Face
                        row = uv_col.row(align=True)
                        row.scale_y = 1.2
                        row.operator("mesh.select_mode", text="Vertex", icon='VERTEXSEL').type = 'VERT'
                        row.operator("mesh.select_mode", text="Edge", icon='EDGESEL').type = 'EDGE'
                        row.operator("mesh.select_mode", text="Face", icon='FACESEL').type = 'FACE'

                        # Sharp | Seam | Lixeira
                        row = uv_col.row(align=True)
                        row.scale_y = 1.2
                        row.alignment = 'EXPAND'
                        row.operator("epictoolbag.mark_sharp", text="Sharp", icon='NONE')
                        row.operator("epictoolbag.mark_seam", text="Seam", icon='NONE')
                        row.operator("epictoolbag.clear_sharp_seam", text="", icon='TRASH')

                        # Unwrap com espaçamento sutil
                        uv_col.separator(factor=1.0)
                        row = uv_col.row(align=True)
                        row.scale_y = 1.5
                        row.operator("uv.unwrap", text="Unwrap!")
                                                
    def draw_imports_tab(self, layout, context, scene):
        addon_prefs = context.preferences.addons[__package__].preferences

        icon = 'DOWNARROW_HLT' if scene.expand_imports else 'RIGHTARROW'
        row = layout.row()
        row.scale_y = 1.5
        row.prop(scene, "expand_imports", icon=icon, text="Import", emboss=True)

        if scene.expand_imports:
            box = layout.box()
            
            row = box.row(align=True)
            row.scale_y = 1.5
            row.prop(addon_prefs, "assets_type", text="")
            row.prop(addon_prefs, "assets_dir", text="")

            row = box.row(align=True)
            row.scale_y = 1.5
            row.operator("epictoolbag.confirm_assets_dir", text="Import Assets", icon='IMPORT')
            row.operator("epictoolbag.clear_assets_dir", text="", icon='TRASH')
                    
    def draw_render_tab(self, layout, context):
        box = layout.box()
        col = box.column(align=True)

        # Propriedade de HDRI
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(context.scene, "hdri_enum", text="")

        pcoll = preview_collections.get("hdri_previews")
        if pcoll:
            # Container para o template_icon_view e navegação
            row = col.row(align=True)
            
            # Botão de seta para esquerda preenchendo verticalmente
            left_col = row.column(align=True)
            left_col.scale_x = 1
            
            # Cria uma box para preencher verticalmente
            left_box = left_col.box()
            left_box_col = left_box.column(align=True)
            left_box_col.scale_y = 7.5  # Tamanho do Arrow
            
            # Botão de navegação para esquerda
            left_arrow = left_box_col.operator("epictoolbag.navigate_hdri", text="", icon='TRIA_LEFT')
            left_arrow.direction = 'PREV'
            
            # Área de thumbnails
            thumb_col = row.column(align=True)
            thumb_col.template_icon_view(context.scene, "hdri_enum", show_labels=True, scale=8.0)
            
            # Botão de seta para direita preenchendo verticalmente
            right_col = row.column(align=True)
            right_col.scale_x = 1
            
            # Cria uma box para preencher verticalmente
            right_box = right_col.box()
            right_box_col = right_box.column(align=True)
            right_box_col.scale_y = 7.5  # Tamanho do Arrow
            
            # Botão de navegação para direita
            right_arrow = right_box_col.operator("epictoolbag.navigate_hdri", text="", icon='TRIA_RIGHT')
            right_arrow.direction = 'NEXT'

        col = layout.column(align=True)

        row = col.row(align=True)
        row.scale_y = 1.5
        row.operator("epictoolbag.add_or_apply_hdri", text="Apply HDRI", icon='WORLD')
        row.operator("epictoolbag.remove_hdri", text="", icon='X')

        col.separator()

        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(context.scene, "hdri_rotation_degrees", text="Rotation", icon='ARROW_LEFTRIGHT')

        # Chama o método de renderização
        self.draw_render_section(layout, context)
        self.draw_render_tools_section(layout, context)

    def draw_render_section(self, layout, context):
        scene = context.scene

        row = layout.row()
        row.scale_y = 1.5
        row.prop(scene, "expand_set_controls", 
                icon='DOWNARROW_HLT' if scene.expand_set_controls else 'RIGHTARROW', 
                text="Set Controls")

        if scene.expand_set_controls:
            box = layout.box()
            col = box.column(align=True)

            # Verifica se há uma luz ou câmera selecionada
            selected_obj = context.active_object
            is_light_or_camera = selected_obj and selected_obj.type in {'LIGHT', 'CAMERA'}

            # Botões de criação
            row = col.row(align=True)
            row.scale_y = 1.5
            row.operator("epictoolbag.create_light", text="Add Light", icon='LIGHT')
            row.operator("epictoolbag.create_camera", text="Add Camera", icon='CAMERA_DATA')
            row.operator("epictoolbag.remove_light_camera", text="", icon='X')

            # Nota informativa em um box com texto brando
            if not is_light_or_camera:
                box_info = col.box()
                row_info = box_info.row()
                row_info.alignment = 'CENTER'
                row_info.label(text="Select a Light or Camera", icon='INFO')

            # Adiciona um pequeno espaço
            col.separator(factor=0.5)

            # Se um objeto de luz ou câmera estiver selecionado, mostra propriedades
            if is_light_or_camera:
                if selected_obj.type == 'LIGHT':
                    self.draw_light_properties(col, context)
                elif selected_obj.type == 'CAMERA':
                    self.draw_camera_properties(col, context)

    def draw_light_properties(self, layout, context):
            light_obj = context.active_object
            light_data = light_obj.data

            col = layout.column(align=True)
            col.scale_y = 1.5

            col.prop(light_data, "type", text="")
            col.prop(light_data, "energy", text="Energy")
            col.prop(light_data, "color", text="")

            if light_data.type in {'POINT', 'SUN', 'SPOT'}:
                col.prop(light_data, "shadow_soft_size", text="Radius")

            if light_data.type in {'POINT', 'SUN', 'SPOT', 'AREA'}:
                col.prop(light_data, "use_soft_shadow", text="Soft Falloff")

            row = col.row(align=True)
            row.prop(light_obj, "location", text="", index=0)
            row.prop(light_obj, "location", text="", index=1)
            row.prop(light_obj, "location", text="", index=2)

    def draw_camera_properties(self, layout, context):
        selected_obj = context.active_object
        scene = context.scene

        # Verifica se um objeto de câmera está selecionado
        if selected_obj and selected_obj.type == 'CAMERA':
            camera = selected_obj
            camera_data = camera.data

            col = layout.column(align=True)
            col.scale_y = 1.5

            # Tipo de câmera
            col.prop(camera_data, "type", text="Type")

            col.separator()

            # Localização
            row = col.row(align=True)
            row.prop(camera, "location", text="X", index=0)
            row.prop(camera, "location", text="Y", index=1)
            row.prop(camera, "location", text="Z", index=2)

            col.separator()

            # Rotação
            row = col.row(align=True)
            row.prop(camera, "rotation_euler", text="X", index=0)
            row.prop(camera, "rotation_euler", text="Y", index=1)
            row.prop(camera, "rotation_euler", text="Z", index=2)

            col.separator()

            # Propriedades específicas de câmera
            if camera_data.type in {'PERSP', 'ORTHO'}:
                row = col.row(align=True)
                row.prop(camera_data, "shift_x", text="Shift X")
                row.prop(camera_data, "shift_y", text="Shift Y")

            col.separator()

            # Comprimento focal
            row = col.row(align=True)
            row.prop(camera_data, "lens", text="Focal Length")
            row.operator("view3d.view_camera", text="", icon='OUTLINER_OB_CAMERA')

            col.separator()

            # Profundidade de campo
            col.prop(camera_data.dof, "use_dof", text="Use Depth of Field")
            if camera_data.dof.use_dof:
                row = col.row(align=True)
                row.prop(camera_data.dof, "focus_distance", text="Focus Distance")
                row.prop(camera_data.dof, "aperture_fstop", text="F-Stop")
                    
    def draw_render_tools_section(self, layout, context):
        scene = context.scene

        row = layout.row()
        row.scale_y = 1.5
        row.prop(scene, "expand_render_tools", 
                icon='DOWNARROW_HLT' if scene.expand_render_tools else 'RIGHTARROW', 
                text="Render Tools")

        if scene.expand_render_tools:
            box = layout.box()
            col = box.column(align=True)

            col.scale_y = 1.5
            col.prop(context.scene.render, "engine", text="")
            col.separator()

            col.prop(context.scene, "world_transparent", text="Transparent")
            col.separator()

            ao_settings = context.scene.eevee
            col.prop(ao_settings, "use_gtao", text="Ambient Occlusion")
            if ao_settings.use_gtao:
                col.prop(ao_settings, "gtao_factor", text="Factor")
                col.prop(ao_settings, "gtao_distance", text="Distance")
            col.separator()

            bloom_settings = context.scene.eevee
            col.prop(bloom_settings, "use_bloom", text="Bloom")
            if bloom_settings.use_bloom:
                col.prop(bloom_settings, "bloom_threshold", text="Threshold")
                col.prop(bloom_settings, "bloom_intensity", text="Intensity")
                col.prop(bloom_settings, "bloom_radius", text="Radius")
                col.prop(bloom_settings, "bloom_color", text="Color")
            col.separator()

            col.label(text="Dimensions:")
            col.scale_y = 1.0
            col.prop(context.scene.render, "resolution_x", text="X")
            col.prop(context.scene.render, "resolution_y", text="Y")
            col.prop(context.scene.render, "resolution_percentage", text="%")
            col.separator()

            col.label(text="Output Settings:")
            col.scale_y = 1.0
            col.prop(context.scene.render, "filepath", text="")
            col.prop(context.scene.render, "file_format", text="")
            col.separator()

            # Botões de Render com layout similar a outros elementos
            row = col.row(align=True)
            row.scale_y = 1.5
            row.operator("render.render", text="Render", icon='IMAGE_DATA')
            row.operator("render.render", text="Render Animation", icon='VIEW_CAMERA_UNSELECTED').animation = True
        
classes = [Preferences,EpicToolBagAddonPanel]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    add_properties()

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    remove_properties()
    unload_hdri_previews()

def remove_properties():
    props_to_remove = [
        "custom_enum",
        "expand_column",
        "expand_render",
        "hdri_files",
        "world_transparent",
        "hdri_rotation_degrees",
        "hdri_enum",
        "expand_light_controls",
        "outline_color",
        "modifier_view_mode",
        "expand_uv_outline",
        "expand_imports",
        "expand_camera",
        "expand_effects",
        "cel_shading_settings",
        "shade_steps",
        "dither_fx_settings",
        "dither_pattern",
        "dither_scale",
        "expand_set_controls",
        "expand_render_tools",
        "topology_view_mode",
        "expand_shader_tools",
        "expand_topology_tools",
    ]
    
    addon_prefs = bpy.context.preferences.addons[__package__].preferences
    if hasattr(addon_prefs, 'last_active_material'):
        addon_prefs.clear_last_active_material()
    
    for prop in props_to_remove:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    if hasattr(bpy.types.Preferences, 'last_active_material'):
        del bpy.types.Preferences.last_active_material
    
    if hasattr(bpy.types.WindowManager, "previous_workspace_name"):
        del bpy.types.WindowManager.previous_workspace_name

    if "hdri_previews" in preview_collections:
        del bpy.types.Scene.hdri_enum