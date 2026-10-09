import turtle
import requests
screen = turtle.Screen()
screen.bgcolor("pink")
t = turtle.Turtle()
t.speed(0)

def plotPoly(points, border_color, width):
    t.pencolor(border_color)
    t.pensize(width)
    t.penup()
    t.goto(points[0])
    t.pendown()
    for point in points[1:]:
        t.goto(point)

def plotPoly2(points, border_color, fill_color, width):
    t.fillcolor(fill_color)
    t.pencolor(border_color)
    t.pensize(width)
    t.begin_fill()
    t.penup()
    t.goto(points[0])
    t.pendown()
    for point in points[1:]:
        t.goto(point)
    t.goto(points[0])
    t.end_fill()

def load_json_from_gitee():
    raw_url = "https://gitee.com/Code-jiang/python/raw/master/hongtailang.json"
    try:
        response = requests.get(raw_url)
        response.raise_for_status()

        polygons_data = response.json()
        return polygons_data
    except requests.exceptions.RequestException as e:
        print(f"Error message: {e}")
        return None

if __name__ == "__main__":
    polygons_data = load_json_from_gitee()

    for polygon in polygons_data["polygons"]:
        if "points2" in polygon:
            points = [tuple(point) for point in polygon["points2"]]
            fill_color = polygon.get("fill_color", "black")
            plotPoly2(points, polygon["border_color"], fill_color, polygon["width"])
        else:
            points = [tuple(point) for point in polygon["points"]]
            plotPoly(points, polygon["border_color"], polygon["width"])

t.hideturtle()
turtle.done()