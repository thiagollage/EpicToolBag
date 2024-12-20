'''
    == Epic Toolbag 2.0 ==  

    Epic Toolbag revolutionizes the creation of shaders in Blender, offering a tool that saves time
    for both beginners and professionals. By providing an intuitive interface and automated features,
    it makes the development of complex materials accessible and efficient. Users can modify source
    files in the ../sources folder, customizing the tool to their needs and enhancing their creative
    workflow. For more information, visit the documentation at <https://epictoolbag.gitbook.io/docs/>.

    Developed by Thiago Lage, Epic Toolbag reflects a commitment to open-source software and the Blender
    community. For support, contact thiagollage@gmail.com. Contributions are welcome; visit the project's
    repository for more information.

    You can redistribute it and/or modify it under the terms of the GNU General Public License as published
    by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
    This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
    the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
    License for more details.

    You should have received a copy of the GNU General Public License along with this program. If not, see
    <http://www.gnu.org/licenses/>.
'''

import bpy
import os
import sys
from . import panels, imports, shader, render, remesh

# Configuração das informações do add-on
bl_info = {
    "name": "Epic Toolbag",
    "blender": (2, 80, 0),
    "category": "Tools",
    "description": "Professional shader tools with extensive effects library and one-click application.",
    "author": "Thiago Lage",
    "version": (2, 0),  
    "location": "View3D > Sidebar > Epic Toolbag Tab",
    "warning": "",
    "doc_url": "https://epictoolbag.gitbook.io/docs",
    "tracker_url": "https://report-bugs.netlify.app/",
    "support": "COMMUNITY"
}

# Configuração do caminho para os arquivos fonte
def setup_source_path():
    addon_path = os.path.dirname(os.path.realpath(__file__))
    source_path = os.path.join(addon_path, "source")
    if source_path not in sys.path:
        sys.path.append(source_path)
    return source_path

def register():
    # Configuração inicial dos caminhos
    source_path = setup_source_path()
    
    # Registro dos módulos
    modules = [panels, imports, shader, render, remesh]
    
    # Registro individual de cada módulo
    for module in modules:
        try:
            # Tenta registrar usando o método register do módulo
            if hasattr(module, 'register'):
                module.register()
            
            # Se não tiver método register, tenta registrar classes
            elif hasattr(module, 'classes'):
                for cls in module.classes:
                    bpy.utils.register_class(cls)
            
            print(f"Registered module: {module.__name__}")
        except Exception as e:
            print(f"Error registering module {module.__name__}: {e}")
    
    # Registro das propriedades
    try:
        if hasattr(panels, 'add_properties'):
            panels.add_properties()
    except Exception as e:
        print(f"Error adding properties: {e}")
    
    # Verificação dos arquivos fonte
    try:
        if hasattr(imports, 'verify_source_files'):
            imports.verify_source_files(source_path)
    except Exception as e:
        print(f"Error verifying source files: {e}")

def unregister():
    # Remove propriedades
    try:
        if hasattr(panels, 'remove_properties'):
            panels.remove_properties()
    except Exception as e:
        print(f"Error removing properties: {e}")
    
    # Remove classes registradas
    modules = [remesh, render, shader, imports, panels]  # Ordem inversa
    
    for module in modules:
        try:
            # Tenta desregistrar usando o método unregister do módulo
            if hasattr(module, 'unregister'):
                module.unregister()
            
            # Se não tiver método unregister, tenta desregistrar classes
            elif hasattr(module, 'classes'):
                for cls in reversed(module.classes):
                    bpy.utils.unregister_class(cls)
            
            print(f"Unregistered module: {module.__name__}")
        except Exception as e:
            print(f"Error unregistering module {module.__name__}: {e}")

if __name__ == "__main__":
    register()