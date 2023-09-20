import trimesh
import numpy as np


def clean_mesh(mesh_dict):
    colors_uint8 = (mesh_dict["colors"] * 255).astype(np.uint8)
    mesh = trimesh.Trimesh(
        vertices=mesh_dict["vertices"],
        faces=mesh_dict["triangles"],
        vertex_colors=colors_uint8,
        process=True,
        validate=True,
    )
    print(f"Initial mesh: {mesh}")
    if not mesh.is_winding_consistent:
        print("The mesh's winding order is inconsistent, attempting to fix.")
        mesh.fix_winding()
    if not mesh.is_watertight:
        print("The mesh is not watertight, attempting to fill holes.")
        mesh.fill_holes()

    remove_isolated(mesh)
    mesh.fill_holes()
    decimated_mesh = decimate_mesh(mesh)
    print(f"Decimated mesh: {decimated_mesh}")
    map_nearest_color_vertices(decimated_mesh, mesh)
    return decimated_mesh


def remove_isolated(mesh):
    # Find connected components of the mesh
    cc = trimesh.graph.connected_components(mesh.face_adjacency, min_len=200)
    # Create a mask with the same length as the number of faces in the mesh
    mask = np.zeros(len(mesh.faces), dtype=bool)
    mask[np.concatenate(cc)] = True

    # Update the mesh with the mask
    mesh.update_faces(mask)
    mesh.remove_unreferenced_vertices()


def map_nearest_color_vertices(decimated_mesh, original_mesh):
    tree = original_mesh.kdtree
    _, indices = tree.query(decimated_mesh.vertices)
    decimated_mesh.visual.vertex_colors = original_mesh.visual.vertex_colors[indices]


def decimate_mesh(mesh, ratio=0.1):
    target_face_count = int(len(mesh.faces) * ratio)
    return mesh.simplify_quadric_decimation(target_face_count)
