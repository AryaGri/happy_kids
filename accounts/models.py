from django.db import models
import datetime

emotions = ['гнев', 'скука', 'радость', 'счастье', 'грусть', 'любовь']

class CUsers(models.Model):
    username = models.CharField('логин', max_length=150)
    name = models.CharField('фио', max_length=150)
    date_of_b = models.DateField('дата рождения')
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Администратор'),
        ('doctor', 'Врач'),
        ('parent', 'Родитель'),
        ('child', 'Ребёнок'),
    ], default='child')
    password = models.CharField('пароль', max_length=150)
    is_auth = models.BooleanField(default=False)

    children = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='parents',
        blank=True
    )

    def __str__(self):
        return f'{self.role} {self.name}'


class GameResult(models.Model):
    user = models.ForeignKey(CUsers, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=20, choices=[
        ('Painting', 'Раскраска'),
        ('Dialog', 'Диалог'),
        ('Choice', 'Выбор'),
    ])
    joy = models.IntegerField(default=0)
    sorrow = models.IntegerField(default=0)
    love = models.IntegerField(default=0)
    anger = models.IntegerField(default=0)
    boredom = models.IntegerField(default=0)
    happiness = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Результат игры {self.game_type} для {self.user.username} - Радость: {self.joy} Счастье: {self.happiness} Любовь: {self.love} Грусть: {self.sorrow} Скука: {self.boredom} Агрессия: {self.anger}"

    class Meta:
        verbose_name = "Результат игры"
        verbose_name_plural = "Результаты игр"
        ordering = ['-date']


class Game:
    def __init__(self, game_type, user_id):
        self.game_type = game_type
        self.user_id = user_id
        self.results = []

    def save_result(self, result):
        self.results.append(result)
        print(f"Результат игры {self.game_type} для пользователя {self.user_id} сохранён.")

class Prescription(models.Model):
    child = models.ForeignKey(CUsers, on_delete=models.CASCADE, related_name='prescriptions')
    text = models.TextField('Текст рецепта')
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Рецепт для {self.child.username} от {self.date_created.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ['-date_created']
