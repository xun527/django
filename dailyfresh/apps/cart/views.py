from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
import json

# Create your views here.
#加入购物车
class AddCartView(View):
    # 1.post请求方式
    def post(self,request):
        # 2.获取商品id,数量
        sku_id = request.POST.get('sku_id')
        count = request.POST.get("count")

        # 3.校验参数,判断商品是否存在
        if not all([sku_id,count]):
            return JsonResponse({'code':2,'message':'参数不完整'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code':3,'messagge':'商品不存在'})

        # 4.判断商品数量类型, 库存多少
        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code':4,'message':'参数错误'})
        if count > sku.stock:
            return JsonResponse({'code':5,'message':'库存不足'})

        if request.user.is_authenticated():
        # 5.如果用户已登录,数据保存到redis中

            # 获取商品id
            user_id = request.user.id

            # 购物车 不存在该商品,添加购物记录
            # 购物车存在该商品,累加数量
            redis_conn = get_redis_connection('default')
            origin_count = redis_conn.hget('cart_%s'%user_id,sku_id)

            if origin_count is not None:
                count += int(origin_count)

            redis_conn.hset('cart_%s'%user_id,sku_id)

            cart_num = 0
            cart = redis_conn.hgetall('cart_%s'%user_id)
            for val in cart.values():
                cart_num += int(val)

            return JsonResponse({'code':0,'message':'添加购物车成功','cart_num':cart_num})

        else:
        # 6.如果用户未登录,数据保存到cookie中
        # 获取cookie商品记录
            cart_json = request.COOKIES.get('cart')

            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}

            # 判断商品记录信息
            if sku_id in cart:
                origin_count = cart[sku_id]
                count += origin_count

            cart[sku_id] = count

            # 将购物车字典数据转换为json字符串
            new_cart_json = json.dumps(cart)

            # 计算数量,保存cookie, 返回处理信息
            cart_num = 0
            for val in cart.values():
                cart_num += val

            response = JsonResponse({'code':0,'message':'添加购物车成功','cart_num':cart_num})

            response.set_cookie('cart',new_cart_json)

            return response

#购物车信息:
class CartInfoView(View):
    # 1.get请求方式,提供购物车页面
    def get(self,request):
        # 2.查询购物车数据
        if not request.user.is_authenticated():
            # 用户未登录,从cookie中获取数据
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}
        else:
            # 用户已登录,从redis中获取数据
            redis_conn = get_redis_connection('default')
            user_id = request.user.id
            cart = redis_conn.hgetall('cart_%s'%user_id)


        # 3.遍历购物车,形成模板所需要的数据
        skus = []
        total_amount = 0
        total_count = 0
        for sku_id,count in cart.items():
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                continue


            # 4.获取商品金额,数量,返回结果
            count = int(count)
            amount = sku.price * count
            sku.amount = amount

            sku.count = count
            skus.append(sku)
            total_amount += amount
            total_count += count

        context = {
            'skus':skus,
            'total_amount':total_amount,
            'total_count':total_count
        }

        return render(request,'cart.html',context)


#更新购物车数据
class UpdateCartView(View):
    # 1.post方式请求
    def post(self,request):
        # 2.获取商品id与数量
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 3.校验参数,商品存在,整数库存
        if not all([sku_id,count]):
            return JsonResponse({'code': 2,'message':'参数不完整'})

        try:
            sku = GoodsSKU.objects.get(id = sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code':3,'message':'商品不存在'})

        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code':4,'message':'数量异常'})

        if count > sku.stock:
            return JsonResponse({'code':5,'message':'库存不足'})

        # 4.保存购物车数据
        if not request.user.is_authenticated():

            # 用户未登录,保存在cookie中
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}

            cart[sku_id] = count

            response = JsonResponse({'code':0,'message':'修改成功'})
            response.set_cookie('cart',json.dumps(cart))
            return response
        else:
            # 用户已登录,保存在redis中
            user_id = request.user.id
            redis_conn = get_redis_connection('default')
            redis_conn.hset('cart_%s'&user_id,sku_id,count)

            return JsonResponse({'code':0,'message':'修改成功'})


#删除购物车信息
class DeleteCartView(View):
    # 1.post方式
    def post(self,request):
        sku_id = request.POST.get('sku_id')
        if not sku_id:
            return JsonResponse({'code':1,'message':'参数缺少'})

        # 2.从购物车中删除数据
        if not request.user.is_authenticated():

            # 用户未登录,从cookie中删除
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart = json.loads(cart_json)

                if sku_id in cart:
                    del cart[sku_id]

                    response = JsonResponse({'code':0,'message':'删除成功'})
                    response.set_cookie('cart',json.dumps(cart))
                    return response
        else:

            # 用户已登录,从redis中删除
            redis_conn = get_redis_connection('default')
            user_id = request.user.id

            redis_conn.hdel('cart_%s'%user_id,sku_id)

        return JsonResponse({'code':0,'message':'删除成功'})








