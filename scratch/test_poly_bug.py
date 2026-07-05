from worker.services.counting_service import point_in_polygon

polygon = [[624.18, 397.31], [922.74, 386.5], [738.84, 1011.75], [7.59, 955.5]]
px = 632.1976623535156
py = 192.15896606445312

res = point_in_polygon(px, py, polygon)
print(f"Point: ({px}, {py})")
print(f"Polygon: {polygon}")
print(f"Result: {res}")
