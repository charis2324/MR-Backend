import numpy as np
import trimesh


def split_model_output(image):
    verts = image.verts.detach().cpu().numpy()
    faces = image.faces.cpu().numpy()
    vertex_colors = np.stack(
        [image.vertex_channels[x].detach().cpu().numpy() for x in "RGB"], axis=1
    )
    return verts, faces, vertex_colors


def clean_mesh(verts, faces, vertex_colors):
    colors_uint8 = (vertex_colors * 255).astype(np.uint8)
    mesh = trimesh.Trimesh(
        vertices=verts,
        faces=faces,
        vertex_colors=colors_uint8,
        process=True,
        validate=True,
    )
    print(f"Initial mesh: {mesh}")
    if not mesh.is_winding_consistent:
        print("The mesh's winding order is inconsistent, attempting to fix.")
        mesh.fix_winding()

    remove_isolated(mesh)

    if not mesh.is_watertight:
        print("The mesh is not watertight, attempting to fill holes.")
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
