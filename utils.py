import bpy
import os

def update_library_paths(blend_file):
    """
    Update the library paths for a given blend file.
    
    :param blend_file: Name of the blend file to update
    """
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(addon_dir, "source")
    
    # Debug print statements to verify paths
    print(f"Epic Toolbag - Addon directory: {addon_dir}")
    print(f"Epic Toolbag - Source directory: {source_dir}")
    print(f"Epic Toolbag - Blend file: {blend_file}")

    for lib in bpy.data.libraries:
        lib_path = bpy.path.abspath(lib.filepath)
        if blend_file in lib_path:
            try:
                new_lib_path = os.path.join(source_dir, blend_file)
            except TypeError as e:
                print(f"Epic Toolbag - Error generating path: {e}")
                return

            print(f"Epic Toolbag - New library path: {new_lib_path}")

            if lib_path != new_lib_path:
                lib.filepath = new_lib_path
                lib.reload()

def load_node_group_from_blend(blend_file, node_group_name):
    """
    Load a node group from a blend file.
    
    :param blend_file: Name of the blend file to load from
    :param node_group_name: Name of the node group to load
    """
    blend_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source", blend_file)
    with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
        if node_group_name in data_from.node_groups:
            print(f"Epic Toolbag - Loading node group '{node_group_name}' from {blend_file}")
            data_to.node_groups.append(node_group_name)
        else:
            print(f"Epic Toolbag - Node group '{node_group_name}' not found in {blend_file}.")

def apply_node_group_to_active_object(context, node_group_name):
    """
    Apply a node group to the active object.
    
    :param context: Blender context
    :param node_group_name: Name of the node group to apply
    :return: True if successful, False otherwise
    """
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        print("Epic Toolbag - No active mesh object to apply node group.")
        return False

    # Check if a Geometry Nodes modifier already exists, otherwise create a new one
    geom_node_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES'), None)
    if not geom_node_mod:
        geom_node_mod = obj.modifiers.new(name="GeometryNodes", type='NODES')

    # Assign the node group to the modifier
    node_group = bpy.data.node_groups.get(node_group_name)
    if node_group:
        print(f"Epic Toolbag - Applying node group '{node_group_name}' to active object.")
        geom_node_mod.node_group = node_group
        return True
    
    print(f"Epic Toolbag - Node group '{node_group_name}' not found in data.")
    return False

def apply_material_to_active_object(context, material_name):
    """
    Apply a material to the active object.
    
    :param context: Blender context
    :param material_name: Name of the material to apply
    :return: The applied material
    """
    obj = context.active_object
    mat = bpy.data.materials.get(material_name)
    
    if mat is None:
        print(f"Epic Toolbag - Creating new material: {material_name}")
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True

    # Assign the material to the object if it isn't already
    if not any(slot.material and slot.material.name == material_name for slot in obj.material_slots):
        obj.data.materials.append(mat)
        print(f"Epic Toolbag - Material '{material_name}' assigned to active object.")
    
    obj.active_material_index = len(obj.material_slots) - 1
    return mat

def get_color_ramp(material):
    """
    Get the color ramp node from a material.
    
    :param material: The material to search for a color ramp
    :return: The color ramp node if found, None otherwise
    """
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'VALTORGB':
                print(f"Epic Toolbag - Color ramp node found in material '{material.name}'.")
                return node
    print(f"Epic Toolbag - No color ramp node found in material '{material.name}'." if material else "Material is None.")
    return None