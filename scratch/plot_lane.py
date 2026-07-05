import matplotlib.pyplot as plt
import json

lane_config = {
    'annotation_roi': {'type': 'rectangle', 'x': 3.99, 'y': 335.86, 'width': 1650.5, 'height': 715.22, 'purpose': 'frontend_annotation_only'},
    'lanes': [
        {'lane_id': 'lane_1', 'valid_zone': [[624.18, 397.31], [922.74, 386.5], [738.84, 1011.75], [7.59, 955.5]], 'counting_line': [[371.05, 968.48], [795.09, 388.66]], 'direction': [[825.38, 477.36], [708.55, 654.77]], 'class_allowed': ['car', 'bus', 'truck', 'motorcycle']},
        {'lane_id': 'lane_2', 'valid_zone': [[948.7, 386.5], [1219.13, 386.5], [1612.88, 1009.59], [831.87, 1016.08]], 'counting_line': [[1085.0, 380.0], [1232.11, 1011.75]], 'direction': [[1273.22, 866.8], [1212.64, 600.68]], 'class_allowed': ['car', 'bus', 'truck', 'motorcycle']}
    ]
}

for lane in lane_config["lanes"]:
    vz = lane["valid_zone"]
    vz.append(vz[0]) # close polygon
    xs, ys = zip(*vz)
    plt.plot(xs, ys, label=f'{lane["lane_id"]} valid_zone')
    
    cl = lane["counting_line"]
    cl_xs, cl_ys = zip(*cl)
    plt.plot(cl_xs, cl_ys, label=f'{lane["lane_id"]} counting_line', linewidth=3, linestyle='--')
    
    dir_line = lane["direction"]
    plt.arrow(dir_line[0][0], dir_line[0][1], dir_line[1][0] - dir_line[0][0], dir_line[1][1] - dir_line[0][1], head_width=20, head_length=20, fc='k', ec='k', label=f'{lane["lane_id"]} direction')

plt.gca().invert_yaxis()
plt.legend()
plt.title('Lane Configuration')
plt.savefig('d:/Backend_traffic_flow/scratch/lane_plot.png')
print("Plot saved to d:/Backend_traffic_flow/scratch/lane_plot.png")
