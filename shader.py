import os
import bpy
from bpy.types import Operator
from bpy.props import (
    StringProperty, 
    FloatVectorProperty, 
    FloatProperty, 
    EnumProperty
)
from .utils import update_library_paths, load_node_group_from_blend, apply_node_group_to_active_object, apply_material_to_active_object, get_color_ramp

def get_color_ramp(material):
    """Get the color ramp node from the material if it exists."""
    if material and material.use_nodes:
        return next((node for node in material.node_tree.nodes if node.type == 'VALTORGB'), None)
    return None

class ShaderEffectBase:
    """Base class for shader effects."""
    bl_options = {'REGISTER', 'UNDO'}

    redirect_to_material: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No active mesh object")
            return {'CANCELLED'}

        effect_data = SHADER_EFFECTS[self.effect_type]
        
        existing_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES' and 
                             mod.node_group and mod.node_group.name == effect_data['group']), None)
        
        if existing_mod:
            self.report({'WARNING'}, f"{self.effect_type} FX modifier already exists")
            return {'CANCELLED'}

        update_library_paths(effect_data['file'])
        load_node_group_from_blend(effect_data['file'], effect_data['group'])
        
        if apply_node_group_to_active_object(context, effect_data['group']):
            mat = apply_material_to_active_object(context, effect_data['material'])
            if mat:
                effect_data['setup_function'](self, mat, context)
            
            new_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES' and 
                            mod.node_group and mod.node_group.name == effect_data['group']), None)
            if new_mod:
                new_mod.name = f"{self.effect_type} Effect"
                self.initialize_node_group_inputs(new_mod)
            
            self.report({'INFO'}, f"{self.effect_type} FX applied successfully")
            if self.redirect_to_material:
                context.scene.modifier_view_mode = 'MATERIAL'
            else:
                context.scene.modifier_view_mode = 'MODIFIERS'
            return {'FINISHED'}
        
        self.report({'ERROR'}, f"Failed to apply {self.effect_type} FX")
        return {'CANCELLED'}

    def setup_material(self, material, context):
        """Setup material specific to the effect. To be overridden by subclasses."""
        pass

    def initialize_node_group_inputs(self, modifier):
        if not modifier.node_group:
            return

        for node in modifier.node_group.nodes:
            if node.type in {'GROUP_INPUT', 'GROUP_OUTPUT'}:
                continue
            
            for input in node.inputs:
                if input.is_linked:
                    continue
                
                input_id = input.name
                
                if input.type == 'RGBA' and input.name == 'Outline Color':
                    modifier[input_id] = bpy.context.scene.outline_color
                elif input.type == 'VALUE':
                    modifier[input_id] = input.default_value
                elif input.type == 'VECTOR':
                    modifier[input_id] = input.default_value.copy()
                elif input.type == 'RGBA':
                    modifier[input_id] = input.default_value.copy()
                elif input.type == 'BOOLEAN':
                    modifier[input_id] = input.default_value
                elif input.type == 'INT':
                    modifier[input_id] = input.default_value
                elif input.type == 'STRING':
                    modifier[input_id] = input.default_value
                elif input.type in {'OBJECT', 'IMAGE', 'COLLECTION', 'TEXTURE', 'MATERIAL'}:
                    modifier[input_id] = None

class CreateOutline(Operator, ShaderEffectBase):
    bl_idname = "object.create_outline"
    bl_label = "Create Outline"
    bl_description = "Create an outline effect on the model using Geometry Nodes"
    bl_options = {'REGISTER', 'UNDO'}
    effect_type = 'OUTLINE'
    redirect_to_material = False

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object first.")
            return {'CANCELLED'}

        # Verifica se o objeto tem materiais
        if not obj.data.materials:
            self.report({'ERROR'}, "Object has no materials. Please add a material first.")
            return {'CANCELLED'}

        # Obtém o material ativo
        active_material = obj.active_material
        if not active_material:
            self.report({'ERROR'}, "No active material selected.")
            return {'CANCELLED'}

        # Verifica se já existe um modificador de Outline para este material específico
        existing_outline_mod = next((mod for mod in obj.modifiers 
                                     if mod.type == 'NODES' and 
                                     mod.node_group and 
                                     mod.node_group.name == f"Outline_{active_material.name}"), None)
        
        # Se já existir, não permite adicionar novamente
        if existing_outline_mod:
            self.report({'WARNING'}, f"Outline modifier already exists for material: {active_material.name}")
            return {'CANCELLED'}

        # Get the updated path for the blend file
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        source_dir = os.path.join(addon_dir, "source")
        blend_file_path = os.path.join(source_dir, "CreateOutlineSetup.blend")

        if not os.path.exists(blend_file_path):
            self.report({'ERROR'}, f"File not found: {blend_file_path}")
            return {'CANCELLED'}

        # Load the .blend file
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.node_groups = [name for name in data_from.node_groups]
            data_to.materials = [name for name in data_from.materials]

        # Busca o grupo de nós de contorno original
        original_geom_node_group = bpy.data.node_groups.get("Outline Effects")
        if not original_geom_node_group:
            self.report({'WARNING'}, "Outline Effects node group not found.")
            return {'CANCELLED'}

        try:
            # Cria uma cópia do grupo de nós para este material específico
            new_geom_node_group = original_geom_node_group.copy()
            new_geom_node_group.name = f"Outline_{active_material.name}"

            # Cria um único modificador de nós de geometria para o objeto
            geom_node_mod = obj.modifiers.new(name=f"Outline_{active_material.name}", type='NODES')
            geom_node_mod.node_group = new_geom_node_group
            
            # Configura o modificador
            input_node = new_geom_node_group.nodes.get("Group Input")
            output_node = new_geom_node_group.nodes.get("Group Output")
            
            if input_node and output_node:
                for input_socket in input_node.outputs:
                    if input_socket.name == "Geometry":
                        geom_node_mod[input_socket.identifier] = obj
                
                for output_socket in output_node.inputs:
                    if output_socket.name == "Geometry":
                        geom_node_mod[output_socket.identifier] = obj

            # Cria materiais de contorno específicos para este material
            outline_material = bpy.data.materials.get("Outline Color")
            rim_material = bpy.data.materials.get("Rim Color")

            if outline_material and rim_material:
                # Cria cópias dos materiais de contorno
                new_outline_mat = outline_material.copy()
                new_outline_mat.name = f"FX Outline_{active_material.name}"
                
                new_rim_mat = rim_material.copy()
                new_rim_mat.name = f"FX Rim_{active_material.name}"

                # Adiciona os novos materiais ao objeto
                obj.data.materials.append(new_outline_mat)
                obj.data.materials.append(new_rim_mat)

        except Exception as e:
            self.report({'ERROR'}, f"Error applying Outline effect: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Outline effect applied to material: {active_material.name}")
        return {'FINISHED'}

    def update_outline_properties(self, context):
        obj = context.active_object
        if obj and obj.modifiers:
            outline_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES' and 
                                mod.node_group and mod.node_group.name == "Outline Effects"), None)
            if outline_mod:
                group_node = next((node for node in outline_mod.node_group.nodes if node.type == 'GROUP'), None)
                if group_node and hasattr(group_node, "inputs"):
                    for input in group_node.inputs:
                        if input.name == "Outline Color":
                            input.default_value = context.scene.outline_color
                        # Add other outline properties here if needed

    def force_viewport_update(self, context):
        context.view_layer.update()

class ApplyCelShading(Operator, ShaderEffectBase):
    """Apply cel shading effect to the model."""
    bl_idname = "epictoolbag.apply_cel_shading"
    bl_label = "Apply Cel Shading"
    bl_description = "Apply cel shading effect to the model"
    effect_type = 'CEL'
    redirect_to_material = True

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object first.")
            return {'CANCELLED'}

        # Check if the object has a material
        if not obj.data.materials:
            self.report({'ERROR'}, "Object has no material. Please add a material first.")
            return {'CANCELLED'}

        addon_dir = os.path.dirname(os.path.abspath(__file__))
        source_dir = os.path.join(addon_dir, "source")
        blend_file_path = os.path.join(source_dir, "CelShadingSetup.blend")

        if not os.path.exists(blend_file_path):
            self.report({'ERROR'}, f"File not found: {blend_file_path}")
            return {'CANCELLED'}

        # Get the names of materials in the blend file
        with bpy.data.libraries.load(blend_file_path) as (data_from, _):
            material_names = data_from.materials

        # The exact name of the Cel Shading material
        cel_shading_name = "Cel Shading (EEVEE)"

        if cel_shading_name not in material_names:
            self.report({'ERROR'}, f"'{cel_shading_name}' not found. Available materials: {', '.join(material_names)}")
            return {'CANCELLED'}

        # Import the material
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            data_to.materials = [cel_shading_name]

        # Get the imported material
        cel_shading_material = bpy.data.materials.get(cel_shading_name)

        if not cel_shading_material:
            self.report({'ERROR'}, f"Failed to import material: {cel_shading_name}")
            return {'CANCELLED'}

        # Create a copy of the CelShading material with "FX" prefix
        new_material = cel_shading_material.copy()
        new_material.name = f"FX {cel_shading_material.name}"

        # Apply the new material to the first slot of the object
        obj.data.materials[0] = new_material

        self.report({'INFO'}, f"Cel Shading effect '{new_material.name}' applied successfully.")
        return {'FINISHED'}

    def setup_material(self, material, context):
        # This method is kept for compatibility with ShaderEffectBase, but we're not using it
        pass

class ApplyDitherFX(Operator, ShaderEffectBase):
    """Apply Dither effect to the model."""
    bl_idname = "epictoolbag.dither_fx"  
    bl_label = "Apply Dither FX"
    bl_description = "Apply Dither effect to the model"
    effect_type = 'DITHER'
    redirect_to_material = True

    def execute(self, context):
        # Mantive a implementação igual ao método anterior
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object first.")
            return {'CANCELLED'}

        # Verifica se o objeto tem material
        if not obj.data.materials:
            self.report({'ERROR'}, "Object has no material. Please add a material first.")
            return {'CANCELLED'}

        addon_dir = os.path.dirname(os.path.abspath(__file__))
        source_dir = os.path.join(addon_dir, "source")
        blend_file_path = os.path.join(source_dir, "DitherSetup.blend")

        if not os.path.exists(blend_file_path):
            self.report({'ERROR'}, f"File not found: {blend_file_path}")
            return {'CANCELLED'}

        # Obtém os nomes dos materiais no arquivo .blend
        with bpy.data.libraries.load(blend_file_path) as (data_from, _):
            material_names = data_from.materials

        # Nome exato do material Dither
        dither_fx_name = "Dither"

        if dither_fx_name not in material_names:
            self.report({'ERROR'}, f"'{dither_fx_name}' not found. Available materials: {', '.join(material_names)}")
            return {'CANCELLED'}

        # Importa o material
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            data_to.materials = [dither_fx_name]

        # Obtém o material importado
        dither_fx_material = bpy.data.materials.get(dither_fx_name)

        if not dither_fx_material:
            self.report({'ERROR'}, f"Failed to import material: {dither_fx_name}")
            return {'CANCELLED'}

        # Cria uma cópia do material Dither com prefixo "FX"
        new_material = dither_fx_material.copy()
        new_material.name = f"FX {dither_fx_name}"

        # Aplica o novo material no primeiro slot do objeto
        obj.data.materials[0] = new_material

        self.report({'INFO'}, f"Dither FX effect '{new_material.name}' applied successfully.")
        return {'FINISHED'}
    
    def setup_material(self, material, context):
        # This method is kept for compatibility with ShaderEffectBase, but we're not using it
        pass

# Atualizar o dicionário SHADER_EFFECTS
SHADER_EFFECTS = {
    'OUTLINE': {
        'file': 'CreateOutlineSetup.blend',
        'group': 'Outline Effects',
        'material': 'Outline Material',
        'setup_function': CreateOutline.execute
    },
    'CEL': {
        'file': 'CelShadingSetup.blend',
        'group': None,
        'material': 'Cel Shading (EEVEE)',
        'setup_function': ApplyCelShading.execute
    },
    'DITHER': {
        'file': 'DitherSetup.blend',
        'group': 'Dither',  
        'material': 'Dither',
        'setup_function': ApplyDitherFX.execute
    }
}
                    
class EditImageThumbnail(Operator):
    """Edit the image in the Image Editor."""
    bl_idname = "epictoolbag.edit_image"
    bl_label = "Edit Image"
    image_name: StringProperty()

    def execute(self, context):
        if context.area:
            image = bpy.data.images.get(self.image_name)
            if image:
                context.area.type = 'IMAGE_EDITOR'
                context.space_data.image = image
                self.report({'INFO'}, f"Editing Image: {image.name}")
            else:
                self.report({'ERROR'}, "Image not found")
        else:
            self.report({'ERROR'}, "Invalid context area")
        return {'FINISHED'}
    
class RemoveActiveMaterialSlot(Operator):
    """Remove the active material slot."""
    bl_idname = "object.remove_active_material_slot"
    bl_label = "Remove Active Material Slot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if obj is not None and obj.type == 'MESH' and len(obj.material_slots) > 0:
            mat = obj.material_slots[obj.active_material_index].material
            bpy.ops.object.material_slot_remove()
            if mat and mat.users == 0:
                bpy.data.materials.remove(mat)
            self.report({'INFO'}, "Material Removed")
        else:
            self.report({'WARNING'}, "No material slot to remove")
        return {'FINISHED'}

class RefreshMaterialInputs(Operator):
    """Refresh material inputs."""
    bl_idname = "epictoolbag.refresh_material_inputs"
    bl_label = "Refresh Material Inputs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.active_material:
            self.report({'ERROR'}, "No Materials Selected")
            return {'CANCELLED'}
        
        # Tenta renomear o nó Principled BSDF
        mat = obj.active_material
        if mat.use_nodes:
            principled_node = next((node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
            if principled_node:
                # Personaliza o nome do shader
                principled_node.name = "Principled Shader"
        
        self.report({'INFO'}, "Refreshed Materials")
        return {'FINISHED'}
    
class ToggleExpandColumn(Operator):
    """Toggle expansion of the column."""
    bl_idname = "epictoolbag.toggle_expand_column"
    bl_label = "Expand/Collapse Column"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        
        # Se a aba Shader estiver ativa, alterna a expansão
        if scene.custom_enum == 'SHADER':
            scene.expand_column = False
            # Força um redesenho da área
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        
        return {'FINISHED'}

class ToggleExpandUVCheck(Operator):
    """Toggle expansion of the UV check section."""
    bl_idname = "epictoolbag.toggle_expand_uv_check"
    bl_label = "Toggle UV Check Expansion"

    def execute(self, context):
        context.scene.expand_uv_check = not context.scene.expand_uv_check
        return {'FINISHED'}
    
class PreviewUVEditing(Operator):
    """Preview UV editing and set to UV Editing workspace."""
    bl_idname = "epictoolbag.preview_uv_editing"
    bl_label = "Preview UV Editing"
    bl_description = "Switch to UV Editing workspace and perform automatic unwrap"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def create_uv_editing_workspace(self, context):
        """Cria um novo workspace de UV Editing se não existir"""
        # Nome do novo workspace
        workspace_name = "UV Editing"
        
        # Verifica se já existe um workspace com este nome
        if workspace_name in bpy.data.workspaces:
            # Se já existir, retorna o workspace existente
            return bpy.data.workspaces[workspace_name]
        
        # Cria um novo workspace copiando o workspace atual
        current_workspace = context.window.workspace
        
        # Usa a API correta para criar workspace
        new_workspace = bpy.context.window.workspace.copy()
        new_workspace.name = workspace_name
        
        # Configura as áreas para UV Editing
        for screen in new_workspace.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    # Muda para Image Editor
                    area.type = 'IMAGE_EDITOR'
                    area.spaces[0].mode = 'UV'
        
        return new_workspace

    def execute(self, context):
        # Verifica se já está no workspace de UV Editing
        if context.window.workspace.name.lower() == "uv editing":
            self.report({'WARNING'}, "Already in UV Editing workspace.")
            return {'CANCELLED'}

        # Salva o workspace anterior
        current_workspace = context.window.workspace.name
        context.window_manager["previous_workspace_name"] = current_workspace

        # Garante que está em modo de objeto
        if context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Encontra ou cria o workspace de UV Editing
        uv_editing_workspace = next((workspace for workspace in bpy.data.workspaces if "UV Editing" in workspace.name.lower()), None)
        
        if not uv_editing_workspace:
            uv_editing_workspace = self.create_uv_editing_workspace(context)
            self.report({'INFO'}, "Created new UV Editing workspace.")
        
        # Muda para o workspace de UV Editing
        context.window.workspace = uv_editing_workspace
        self.report({'INFO'}, "Switched to UV Editing workspace.")
        
        # Entra no modo de edição
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Seleciona todos os vértices
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Realiza unwrap automático
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
        
        # Abre o editor de UV
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces[0].mode = 'UV'
                break
        
        self.report({'INFO'}, "Automatic UV unwrap performed.")
        return {'FINISHED'}
        
class RevertWorkspace(Operator):
    """Revert to previous workspace"""
    bl_idname = "epictoolbag.revert_workspace"
    bl_label = "Revert Workspace"
    bl_description = "Return to the previous workspace"

    @classmethod
    def poll(cls, context):
        return "previous_workspace_name" in context.window_manager

    def execute(self, context):
        previous_workspace_name = context.window_manager.get("previous_workspace_name")
        
        if previous_workspace_name:
            # Encontra o workspace anterior
            previous_workspace = next((workspace for workspace in bpy.data.workspaces if workspace.name == previous_workspace_name), None)
            
            if previous_workspace:
                # Volta para o modo de objeto
                if context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                
                # Muda para o workspace anterior
                context.window.workspace = previous_workspace
                
                # Limpa o nome do workspace anterior
                del context.window_manager["previous_workspace_name"]
                
                self.report({'INFO'}, f"Returned to {previous_workspace_name} workspace.")
            else:
                self.report({'ERROR'}, "Previous workspace not found.")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No previous workspace to return to.")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class AddCheckerTexture(Operator):
    """Add a checker texture to the active object."""
    bl_idname = "epictoolbag.add_checker_texture"
    bl_label = "Add Checker Texture"
    bl_options = {'REGISTER', 'UNDO'}

    checker_color1: FloatVectorProperty(
        name="Checker Color 1",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="Color of the first checker"
    )

    checker_color2: FloatVectorProperty(
        name="Checker Color 2",
        subtype='COLOR',
                default=(0.0, 0.0, 0.0),
        min=0.0, max=1.0,
        description="Color of the second checker"
    )

    scale: FloatProperty(
        name="Scale",
        default=5.0,
        min=0.1, max=100.0,
        description="Scale of the checker pattern"
    )

    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH':
            mat = bpy.data.materials.new(name="Checker_Material")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()

            checker_node = nodes.new(type='ShaderNodeTexChecker')
            checker_node.location = (-300, 0)
            checker_node.inputs['Color1'].default_value = (*self.checker_color1, 1)
            checker_node.inputs['Color2'].default_value = (*self.checker_color2, 1)
            checker_node.inputs['Scale'].default_value = self.scale

            material_output = nodes.new(type='ShaderNodeOutputMaterial')
            material_output.location = (100, 0)

            links = mat.node_tree.links
            links.new(checker_node.outputs['Color'], material_output.inputs['Surface'])

            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

            self.report({'INFO'}, "Checker Texture applied")
        else:
            self.report({'ERROR'}, "No mesh object selected")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class RemoveCheckerTexture(Operator):
    """Remove the checker texture from the active object."""
    bl_idname = "epictoolbag.remove_checker_texture"
    bl_label = "Remove Checker Texture"
    bl_options = {'REGISTER', 'UNDO'}  
        
    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH' and obj.active_material and obj.active_material.use_nodes:
            mat = obj.active_material
            nodes = mat.node_tree.nodes

            checker_node_found = any(node for node in nodes if node.type == 'TEX_CHECKER')
            
            if checker_node_found:
                obj.data.materials.clear()
                bpy.data.materials.remove(mat)
                self.report({'INFO'}, "Checker Texture Node and material removed")
            else:
                self.report({'WARNING'}, "No Checker Texture Node found in the active material")
        else:
            self.report({'ERROR'}, "No suitable material found to remove a Checker Texture Node")
        return {'FINISHED'}
    
class AddPrincipledMaterial(Operator):
    """Add a new Principled BSDF material to the active object."""
    bl_idname = "object.add_principled_material"
    bl_label = "Add Principled Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            mat = bpy.data.materials.new(name="New Material")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            node_output = nodes.new(type='ShaderNodeOutputMaterial')
            node_principled.location = (0, 0)
            node_output.location = (200, 0)
            links = mat.node_tree.links
            link = links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            self.report({'INFO'}, "Principled Material added")
        else:
            self.report({'ERROR'}, "No mesh object selected")
        return {'FINISHED'}
    

    
class ExpandMiscSection(Operator):
    """Expand the miscellaneous section."""
    bl_idname = "epictoolbag.expand_misc_section"
    bl_label = "Expand Misc Section"

    def execute(self, context):
        context.scene.expand_uv_outline = True
        return {'FINISHED'}

class CollapseMiscSection(Operator):
    """Collapse the miscellaneous section."""
    bl_idname = "epictoolbag.collapse_misc_section"
    bl_label = "Collapse Misc Section"

    def execute(self, context):
        context.scene.expand_uv_outline = False
        return {'FINISHED'}

class UpdateGeometryNodes(Operator):
    bl_idname = "epictoolbag.update_geometry_nodes"
    bl_label = "Update Geometry Nodes"
    bl_description = "Update Geometry Nodes for Epic Shader effects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object
        for mod in obj.modifiers:
            if mod.type == 'NODES' and mod.node_group:
                self.update_modifier_and_node_group(mod)
                self.report({'INFO'}, f"Updated {mod.name}")
        return {'FINISHED'}

    def update_modifier_and_node_group(self, modifier):
        if modifier.node_group:
            for node in modifier.node_group.nodes:
                for input in node.inputs:
                    input_id = f"{node.name}_{input.name}"
                    if input_id in modifier:
                        # Atualiza o valor do nó com o valor do modificador
                        input.default_value = modifier[input_id]
                    elif hasattr(input, 'default_value'):
                        # Se o input não está no modificador, mas tem um valor padrão, use-o no modificador
                        modifier[input_id] = input.default_value

    def invoke(self, context, event):
        return self.execute(context)

class RemoveShaderEffect(Operator):
    """Remove the applied shader effect."""
    bl_idname = "epictoolbag.remove_shader_effect"
    bl_label = "Remove Shader Effect"
    bl_description = "Remove the applied shader effect"
    bl_options = {'REGISTER', 'UNDO'}

    effect_type: StringProperty(
        name="Effect Type",
        description="Type of effect to remove",
        default=""
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        effect_data = SHADER_EFFECTS.get(self.effect_type)
        if not effect_data:
            self.report({'ERROR'}, f"Unknown effect type: {self.effect_type}")
            return {'CANCELLED'}

        for mod in obj.modifiers:
            if mod.type == 'NODES' and mod.node_group and mod.node_group.name == effect_data['group']:
                obj.modifiers.remove(mod)

        for i, slot in enumerate(obj.material_slots):
            if slot.material and slot.material.name == effect_data['material']:
                obj.active_material_index = i
                bpy.ops.object.material_slot_remove()
                break

        self.report({'INFO'}, f"Removed {effect_data['group']} effect")
        return {'FINISHED'}

class EditImageThumbnail(Operator):
    """Edit the image in the Image Editor."""
    bl_idname = "epictoolbag.edit_image"
    bl_label = "Edit Image"
    image_name: StringProperty()

    def execute(self, context):
        if context.area:
            image = bpy.data.images.get(self.image_name)
            if image:
                context.area.type = 'IMAGE_EDITOR'
                context.space_data.image = image
                self.report({'INFO'}, f"Editing Image: {image.name}")
            else:
                self.report({'ERROR'}, "Image not found")
        else:
            self.report({'ERROR'}, "Invalid context area")
        return {'FINISHED'}
    
class RemoveActiveMaterialSlot(Operator):
    """Remove the active material slot."""
    bl_idname = "object.remove_active_material_slot"
    bl_label = "Remove Active Material Slot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if obj is not None and obj.type == 'MESH' and len(obj.material_slots) > 0:
            mat = obj.material_slots[obj.active_material_index].material
            bpy.ops.object.material_slot_remove()
            if mat and mat.users == 0:
                bpy.data.materials.remove(mat)
            self.report({'INFO'}, "Material Removed")
        else:
            self.report({'WARNING'}, "No material slot to remove")
        return {'FINISHED'}

class AddColorRampPoint(Operator):
    """Add a new point to the Color Ramp of the active material."""
    bl_idname = "epic_shader.add_color_ramp_point"  # Mantenha um ID consistente
    bl_label = "Add Color Ramp Point"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if obj and obj.active_material:
            color_ramp = get_color_ramp(obj.active_material)
            if color_ramp:
                color_ramp.color_ramp.elements.new(0.5)
                self.report({'INFO'}, "Point added to Color Ramp")
            else:
                self.report({'WARNING'}, "No Color Ramp found in the active material")
        else:
            self.report({'ERROR'}, "No active object or material")
        return {'FINISHED'}


class RefreshMaterialInputs(Operator):
    """Refresh material inputs."""
    bl_idname = "epictoolbag.refresh_material_inputs"
    bl_label = "Refresh Material Inputs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not context.active_object or context.active_object.type != 'MESH' or not context.active_object.active_material:
            self.report({'ERROR'}, "No Materials Selected")
            return {'CANCELLED'}
        self.report({'INFO'}, "Refreshed Materials")
        return {'FINISHED'}

class ToggleExpandColumn(Operator):
    """Toggle expansion of the column."""
    bl_idname = "epictoolbag.toggle_expand_column"
    bl_label = "Expand/Collapse Column"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        scene.expand_column = not scene.expand_column
        return {'FINISHED'}

class ToggleExpandUVCheck(Operator):
    """Toggle expansion of the UV check section."""
    bl_idname = "epictoolbag.toggle_expand_uv_check"
    bl_label = "Toggle UV Check Expansion"

    def execute(self, context):
        context.scene.expand_uv_check = not context.scene.expand_uv_check
        return {'FINISHED'}

class AddCheckerTexture(Operator):
    """Add a checker texture to the active object."""
    bl_idname = "epictoolbag.add_checker_texture"
    bl_label = "Add Checker Texture"
    bl_options = {'REGISTER', 'UNDO'}

    checker_color1: FloatVectorProperty(
        name="Checker Color 1",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="Color of the first checker"
    )

    checker_color2: FloatVectorProperty(
        name="Checker Color 2",
        subtype='COLOR',
                default=(0.0, 0.0, 0.0),
        min=0.0, max=1.0,
        description="Color of the second checker"
    )

    scale: FloatProperty(
        name="Scale",
        default=5.0,
        min=0.1, max=100.0,
        description="Scale of the checker pattern"
    )

    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH':
            mat = bpy.data.materials.new(name="Checker_Material")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()

            checker_node = nodes.new(type='ShaderNodeTexChecker')
            checker_node.location = (-300, 0)
            checker_node.inputs['Color1'].default_value = (*self.checker_color1, 1)
            checker_node.inputs['Color2'].default_value = (*self.checker_color2, 1)
            checker_node.inputs['Scale'].default_value = self.scale

            material_output = nodes.new(type='ShaderNodeOutputMaterial')
            material_output.location = (100, 0)

            links = mat.node_tree.links
            links.new(checker_node.outputs['Color'], material_output.inputs['Surface'])

            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

            self.report({'INFO'}, "Checker Texture applied")
        else:
            self.report({'ERROR'}, "No mesh object selected")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class RemoveCheckerTexture(Operator):
    """Remove the checker texture from the active object."""
    bl_idname = "epictoolbag.remove_checker_texture"
    bl_label = "Remove Checker Texture"
    bl_options = {'REGISTER', 'UNDO'}  
        
    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH' and obj.active_material and obj.active_material.use_nodes:
            mat = obj.active_material
            nodes = mat.node_tree.nodes

            checker_node_found = any(node for node in nodes if node.type == 'TEX_CHECKER')
            
            if checker_node_found:
                obj.data.materials.clear()
                bpy.data.materials.remove(mat)
                self.report({'INFO'}, "Checker Texture Node and material removed")
            else:
                self.report({'WARNING'}, "No Checker Texture Node found in the active material")
        else:
            self.report({'ERROR'}, "No suitable material found to remove a Checker Texture Node")
        return {'FINISHED'}
    
class AddPrincipledMaterial(Operator):
    """Add a new Principled BSDF material to the active object."""
    bl_idname = "object.add_principled_material"
    bl_label = "Add Principled Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            mat = bpy.data.materials.new(name="New Material")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            node_output = nodes.new(type='ShaderNodeOutputMaterial')
            node_principled.location = (0, 0)
            node_output.location = (200, 0)
            links = mat.node_tree.links
            link = links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            self.report({'INFO'}, "Principled Material added")
        else:
            self.report({'ERROR'}, "No mesh object selected")
        return {'FINISHED'}
       
class ExpandTopologySection(Operator):
    """Expand the Topology section."""
    bl_idname = "epictoolbag.expand_topology_section"
    bl_label = "Expand Topology Section"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.expand_column = True
        return {'FINISHED'}

class CollapseTopologySection(Operator):
    """Collapse the Topology section."""
    bl_idname = "epictoolbag.collapse_topology_section"
    bl_label = "Collapse Topology Section"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.expand_column = False
        return {'FINISHED'}

class UpdateGeometryNodes(Operator):
    bl_idname = "epictoolbag.update_geometry_nodes"
    bl_label = "Update Geometry Nodes"
    bl_description = "Update Geometry Nodes for Epic Shader effects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        obj = context.object
        for mod in obj.modifiers:
            if mod.type == 'NODES' and mod.node_group:
                self.update_modifier_and_node_group(mod)
                self.report({'INFO'}, f"Updated {mod.name}")
        return {'FINISHED'}

    def update_modifier_and_node_group(self, modifier):
        if modifier.node_group:
            for node in modifier.node_group.nodes:
                for input in node.inputs:
                    input_id = f"{node.name}_{input.name}"
                    if input_id in modifier:
                        # Atualiza o valor do nó com o valor do modificador
                        input.default_value = modifier[input_id]
                    elif hasattr(input, 'default_value'):
                        # Se o input não está no modificador, mas tem um valor padrão, use-o no modificador
                        modifier[input_id] = input.default_value

    def invoke(self, context, event):
        return self.execute(context)

def apply_principled_material(obj):
    """Aplica um material Principled BSDF padrão ao objeto"""
    mat = bpy.data.materials.new(name=f"Principled {obj.name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    # Adiciona nó Principled BSDF
    principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (0, 0)
    
    # Adiciona nó de saída de material
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (200, 0)
    
    # Conecta os nós
    links = mat.node_tree.links
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])
    
    # Adiciona o material ao objeto
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

# Modifique cada operador de primitiva para incluir a aplicação do material
class CreatePrimitiveCube(bpy.types.Operator):
    bl_idname = "epictoolbag.create_primitive_cube"
    bl_label = "Create Cube"
    bl_description = "Create a Cube primitive mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=2, align='WORLD', location=(0, 0, 0))
        obj = context.active_object
        apply_principled_material(obj)
        return {'FINISHED'}

class CreatePrimitiveUVSphere(bpy.types.Operator):
    bl_idname = "epictoolbag.create_primitive_uv_sphere"
    bl_label = "Create UV Sphere"
    bl_description = "Create a UV Sphere primitive mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, align='WORLD', location=(0, 0, 0))
        obj = context.active_object
        apply_principled_material(obj)
        return {'FINISHED'}

class CreatePrimitiveCylinder(bpy.types.Operator):
    bl_idname = "epictoolbag.create_primitive_cylinder"
    bl_label = "Create Cylinder"
    bl_description = "Create a Cylinder primitive mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, align='WORLD', location=(0, 0, 0))
        obj = context.active_object
        apply_principled_material(obj)
        return {'FINISHED'}

class CreatePrimitiveCone(bpy.types.Operator):
    bl_idname = "epictoolbag.create_primitive_cone"
    bl_label = "Create Cone"
    bl_description = "Create a Cone primitive mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_cone_add(radius1=1, depth=2, align='WORLD', location=(0, 0, 0))
        obj = context.active_object
        apply_principled_material(obj)
        return {'FINISHED'}

class CreatePrimitiveTorus(bpy.types.Operator):
    bl_idname = "epictoolbag.create_primitive_torus"
    bl_label = "Create Torus"
    bl_description = "Create a Torus primitive mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=1, 
            minor_radius=0.25, 
            major_segments=48, 
            minor_segments=12, 
            align='WORLD', 
            location=(0, 0, 0)
        )
        obj = context.active_object
        apply_principled_material(obj)
        return {'FINISHED'}

class CreatePrimitivePlane(bpy.types.Operator):
    bl_idname = "epictoolbag.create_primitive_plane"
    bl_label = "Create Plane"
    bl_description = "Create a Plane primitive mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_plane_add(size=2, align='WORLD', location=(0, 0, 0))
        obj = context.active_object
        apply_principled_material(obj)
        return {'FINISHED'}
  
class AddSpecificModifier(Operator):
    """Add a specific modifier to the active object"""
    bl_idname = "epictoolbag.add_specific_modifier"
    bl_label = "Add Specific Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_type: EnumProperty(
        name="Modifier Type",
        description="Select a modifier to add",
        items=[
            ('ARRAY', "Array", "Add Array modifier", 'MOD_ARRAY', 0),
            ('BEVEL', "Bevel", "Add Bevel modifier", 'MOD_BEVEL', 1),
            ('BOOLEAN', "Boolean", "Add Boolean modifier", 'MOD_BOOLEAN', 2),
            ('CURVE', "Curve", "Add Curve modifier", 'MOD_CURVE', 3),
            ('DECIMATE', "Decimate", "Add Decimate modifier", 'MOD_DECIM', 4),
            ('MIRROR', "Mirror", "Add Mirror modifier", 'MOD_MIRROR', 5),
            ('MULTIRES', "Multiresolution", "Add Multiresolution modifier", 'MOD_MULTIRES', 6),
            ('SMOOTH', "Smooth", "Add Smooth modifier", 'MOD_SMOOTH', 7),
            ('SUBSURF', "Subdivision Surface", "Add Subdivision Surface modifier", 'MOD_SUBSURF', 8),
            ('SOLIDIFY', "Solidify", "Add Solidify modifier", 'MOD_SOLIDIFY', 9),
            ('SHRINKWRAP', "Shrinkwrap", "Add Shrinkwrap modifier", 'MOD_SHRINKWRAP', 10),
            # Add other modifiers here if needed
        ]
    )

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            try:
                bpy.ops.object.modifier_add(type=self.modifier_type)
                
                # Additional setup for specific modifiers
                if self.modifier_type == 'BOOLEAN':
                    bool_mod = obj.modifiers[-1]
                    bool_mod.operation = 'DIFFERENCE'  # Default setting
                
                elif self.modifier_type == 'NODES':
                    geom_mod = obj.modifiers[-1]
                    
                    # Create a basic node group
                    node_group = bpy.data.node_groups.new(name="Geometry Nodes", type='GeometryNodeTree')
                    
                    # Add default input and output nodes
                    input_node = node_group.nodes.new('NodeGroupInput')
                    output_node = node_group.nodes.new('NodeGroupOutput')
                    
                    # Set the modifier with the new node group
                    geom_mod.node_group = node_group
                
                self.report({'INFO'}, f"{self.modifier_type} modifier added")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to add {self.modifier_type} modifier: {str(e)}")
        else:
            self.report({'ERROR'}, "No mesh object selected")
        return {'CANCELLED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "modifier_type", text="Select Modifier")
                
class CreateText(bpy.types.Operator):
    bl_idname = "epictoolbag.create_text"
    bl_label = "Add Text"
    bl_description = "Create a new Text object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.text_add(align='WORLD', location=(0, 0, 0))
        return {'FINISHED'}
    
class AddTextMaterial(bpy.types.Operator):
    """Add a new material for Text object"""
    bl_idname = "epictoolbag.add_text_material"
    bl_label = "Add Text Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'FONT':
            mat = bpy.data.materials.new(name="Material Text")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            
            # Adiciona nó Principled BSDF
            node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            node_output = nodes.new(type='ShaderNodeOutputMaterial')
            node_principled.location = (0, 0)
            node_output.location = (200, 0)
            
            # Conecta os nós
            links = mat.node_tree.links
            links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
            
            # Adiciona o material ao objeto
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
            
            self.report({'INFO'}, "Text Material added")
        else:
            self.report({'ERROR'}, "No text object selected")
        return {'FINISHED'}

class SmartUVUnwrap(bpy.types.Operator):
    """Perform Smart UV Unwrap on the active object"""
    bl_idname = "epictoolbag.smart_uv_unwrap"
    bl_label = "Smart UV Unwrap"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        
        # Entrar no modo de edição
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Selecionar todos os vértices
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Adiciona um novo UV map com um nome incremental
        uv_count = len(obj.data.uv_layers)
        new_uv_map = obj.data.uv_layers.new(name=f"SmartUV_{uv_count + 1}")
        
        # Ativa o novo UV map
        obj.data.uv_layers.active = new_uv_map
        
        # Realizar Smart UV Unwrap
        bpy.ops.uv.smart_project(
            angle_limit=66.0, 
            island_margin=0.02, 
            area_weight=0.0, 
            correct_aspect=True, 
            scale_to_bounds=False
        )
        
        # Voltar para o modo de objeto
        bpy.ops.object.mode_set(mode='OBJECT')
        
        self.report({'INFO'}, f"Smart UV Unwrap {uv_count + 1} completed")
        return {'FINISHED'}
    
class MarkSharp(bpy.types.Operator):
    """Mark edges as sharp"""
    bl_idname = "epictoolbag.mark_sharp"
    bl_label = "Mark Sharp"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        bpy.ops.mesh.mark_sharp()
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class ClearSharp(bpy.types.Operator):
    """Clear sharp edges"""
    bl_idname = "epictoolbag.clear_sharp"
    bl_label = "Clear Sharp"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        bpy.ops.mesh.clear_sharp()
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class MarkSeam(bpy.types.Operator):
    """Mark edges as seam"""
    bl_idname = "epictoolbag.mark_seam"
    bl_label = "Mark Seam"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        bpy.ops.mesh.mark_seam()
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class ClearSeam(bpy.types.Operator):
    """Clear seam edges"""
    bl_idname = "epictoolbag.clear_seam"
    bl_label = "Clear Seam"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        bpy.ops.mesh.clear_seam()
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        # Adiciona uma verificação para garantir que apenas objetos de malha possam usar o operador
        return context.active_object is not None and context.active_object.type == 'MESH'

class ToggleExpandShaderTools(Operator):
    """Toggle expansion of the shader tools section."""
    bl_idname = "epictoolbag.toggle_expand_shader_tools"
    bl_label = "Toggle Shader Tools Expansion"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.expand_shader_tools = not context.scene.expand_shader_tools
        return {'FINISHED'}

class ToggleExpandTopologyTools(Operator):
    """Toggle expansion of the topology tools section."""
    bl_idname = "epictoolbag.toggle_expand_topology_tools"
    bl_label = "Toggle Topology Tools Expansion"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.expand_topology_tools = not context.scene.expand_topology_tools
        return {'FINISHED'}
    
class ClearSharpAndSeam(bpy.types.Operator):
    """Clear Sharp and Seam from selected edges"""
    bl_idname = "epictoolbag.clear_sharp_seam"
    bl_label = "Clear Sharp and Seam"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Modo de edição
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Limpar Sharp
        try:
            bpy.ops.mesh.mark_sharp(clear=True)
        except Exception as e:
            print(f"Error clearing sharp: {e}")
        
        # Limpar Seam
        try:
            bpy.ops.mesh.mark_seam(clear=True)
        except Exception as e:
            print(f"Error clearing seam: {e}")
        
        return {'FINISHED'}
    
class convert_text_to_mesh(bpy.types.Operator):
    bl_idname = "epictoolbag.convert_text_to_mesh"
    bl_label = "Apply Convert to Mesh"
    bl_description = "Convert selected text object to mesh"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and isinstance(obj.data, bpy.types.TextCurve)

    def execute(self, context):
        bpy.ops.object.convert(target='MESH')
        return {'FINISHED'}
    
import bpy

classes = [
    UpdateGeometryNodes,
    ApplyCelShading,
    CreateOutline,
    ApplyDitherFX,
    RemoveShaderEffect,
    EditImageThumbnail,
    RemoveActiveMaterialSlot,
    RefreshMaterialInputs,
    ToggleExpandColumn,
    ToggleExpandUVCheck,
    PreviewUVEditing,
    RevertWorkspace,
    AddCheckerTexture,
    RemoveCheckerTexture,
    AddColorRampPoint, 
    AddPrincipledMaterial,
    ExpandMiscSection,
    CollapseMiscSection,
    CreatePrimitiveCube,
    CreatePrimitiveUVSphere,
    CreatePrimitiveCylinder,
    CreatePrimitiveCone,
    CreatePrimitiveTorus,
    CreatePrimitivePlane,
    AddSpecificModifier,
    CreateText,
    AddTextMaterial,
    SmartUVUnwrap,
    MarkSharp,
    ClearSharp,
    MarkSeam,
    ClearSeam,
    ExpandTopologySection,
    CollapseTopologySection,
    ToggleExpandShaderTools,
    ToggleExpandTopologyTools,
    ClearSharpAndSeam,
    convert_text_to_mesh
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()